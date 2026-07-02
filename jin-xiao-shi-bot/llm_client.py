# -*- coding: utf-8 -*-
"""
DeepSeek API 客户端模块
"""

import os
import time
import logging
from typing import Optional, List, Dict, Any
from openai import OpenAI, APIConnectionError, APITimeoutError, RateLimitError

logger = logging.getLogger(__name__)

# 重试的异常类型：网络问题、超时、限流、5xx 服务端错误
RETRYABLE_EXCEPTIONS = (APIConnectionError, APITimeoutError, RateLimitError)


class LLMClient:
    """DeepSeek API 客户端封装"""
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
        system_prompt: str = None,
        timeout: float = 30.0,
        max_retries: int = 2
    ):
        """
        初始化 LLM 客户端

        Args:
            api_key: API 密钥
            base_url: API 地址
            model: 模型名称
            system_prompt: 系统提示词
            timeout: 单次请求超时时间（秒）
            max_retries: 失败后的最大重试次数（不含首次请求）
        """
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.timeout = timeout
        self.max_retries = max_retries

        # 初始化 OpenAI 客户端（DeepSeek 兼容 OpenAI 格式）
        # 关闭 SDK 自带重试，由 ask() 统一控制退避策略
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=0
        )
    
    def _default_system_prompt(self) -> str:
        """默认系统提示词"""
        return """你是一个专业的金蝶实施顾问，名字叫"金小石"。
你的职责是帮助用户解答金蝶 ERP 实施相关的问题。
自我介绍时只说"我是金小石，金蝶实施顾问"，不要展开介绍职责和能力，除非用户明确追问。

回答要求：
1. 基于提供的知识库内容准确回答，不确定或知识库中没有的内容，直接说明"在知识库中未找到相关内容"，不要编造
2. 只说和问题直接相关的内容，不铺垫、不总结、不加"温馨提示"之类的套话
3. 涉及操作步骤时，直接用"1. 2. 3."列出具体动作（点哪个菜单、填哪个字段），跳过背景解释
4. 涉及单据、字段、配置项名称时用原文准确表述，不要简化或意译
5. 篇幅控制在能让用户一次看懂并照做的最小长度，避免同一意思重复表达"""
    
    def ask(
        self,
        question: str,
        context: str = None,
        history: List[Dict[str, str]] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7
    ) -> str:
        """
        向 LLM 提问

        Args:
            question: 用户问题
            context: 知识库上下文
            history: 历史对话消息列表，每项为 {"role": "user"/"assistant", "content": "..."}
            max_tokens: 最大生成 token 数
            temperature: 温度参数（0-2，越低越确定性）

        Returns:
            LLM 回答
        """
        messages = []

        # 添加系统提示词
        system_content = self.system_prompt
        if context:
            system_content += f"\n\n【知识库参考内容】\n{context}\n\n【重要】请基于以上知识库内容回答用户问题。如果知识库中没有相关信息，请明确说明。"

        messages.append({
            "role": "system",
            "content": system_content
        })

        # 添加历史对话
        if history:
            messages.extend(history)

        # 添加用户问题
        messages.append({
            "role": "user",
            "content": question
        })

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=False
                )

                answer = response.choices[0].message.content

                # 截断超长回答
                if len(answer) > 4000:
                    answer = answer[:4000] + "\n\n（回答已截断）"

                return answer

            except RETRYABLE_EXCEPTIONS as e:
                last_error = e
                if attempt < self.max_retries:
                    delay = 2 ** attempt  # 1s, 2s, 4s...
                    logger.warning(
                        f"LLM 调用失败（第 {attempt + 1} 次），{delay}s 后重试: {e}"
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"LLM 调用重试 {self.max_retries} 次后仍失败: {e}")
            except Exception as e:
                logger.error(f"LLM 调用失败: {e}")
                return f"抱歉，AI 服务暂时不可用，请稍后重试。错误信息: {str(e)}"

        return f"抱歉，AI 服务暂时不可用，请稍后重试。错误信息: {str(last_error)}"
    
    def ask_stream(
        self,
        question: str,
        context: str = None,
        max_tokens: int = 2000,
        temperature: float = 0.7
    ):
        """
        流式提问（用于返回迭代器）
        
        Args:
            question: 用户问题
            context: 知识库上下文
            max_tokens: 最大生成 token 数
            temperature: 温度参数
        
        Yields:
            回答片段
        """
        try:
            messages = []
            
            system_content = self.system_prompt
            if context:
                system_content += f"\n\n【知识库参考内容】\n{context}\n\n请基于以上知识库内容回答用户问题。"
            
            messages.append({
                "role": "system",
                "content": system_content
            })
            
            messages.append({
                "role": "user",
                "content": question
            })
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True
            )
            
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"LLM 流式调用失败: {e}")
            yield f"抱歉，AI 服务暂时不可用。错误信息: {str(e)}"
    
    def set_system_prompt(self, prompt: str):
        """设置系统提示词"""
        self.system_prompt = prompt


def create_llm_client(
    api_key: str = None,
    base_url: str = None,
    model: str = None,
    system_prompt: str = None
) -> LLMClient:
    """
    创建 LLM 客户端的便捷函数
    
    Args:
        api_key: API 密钥
        base_url: API 地址
        model: 模型名称
        system_prompt: 系统提示词
    
    Returns:
        LLMClient 实例
    """
    # 尝试从 config 读取配置
    try:
        from config import (
            DEEPSEEK_API_KEY,
            DEEPSEEK_BASE_URL,
            DEEPSEEK_MODEL,
            SYSTEM_PROMPT as CONFIG_SYSTEM_PROMPT
        )
        
        if api_key is None:
            api_key = os.environ.get("DEEPSEEK_API_KEY", DEEPSEEK_API_KEY)
        if base_url is None:
            base_url = os.environ.get("DEEPSEEK_BASE_URL", DEEPSEEK_BASE_URL)
        if model is None:
            model = os.environ.get("DEEPSEEK_MODEL", DEEPSEEK_MODEL)
        if system_prompt is None:
            system_prompt = CONFIG_SYSTEM_PROMPT
            
    except ImportError:
        # config 不存在，使用默认值
        if api_key is None:
            api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if base_url is None:
            base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        if model is None:
            model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    
    if not api_key:
        raise ValueError("未设置 DeepSeek API Key")
    
    return LLMClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
        system_prompt=system_prompt
    )


if __name__ == "__main__":
    # 测试代码
    client = create_llm_client()
    response = client.ask("采购订单的审批流如何配置？")
    print(response)
