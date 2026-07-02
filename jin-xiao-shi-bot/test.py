#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速测试脚本 - 验证各模块是否正常工作
"""

import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_config():
    """测试配置模块"""
    print("=" * 50)
    print("测试配置模块...")
    try:
        from config import (
            WECOM_BOT_ID, WECOM_SECRET, WS_URL,
            DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
            KNOWLEDGE_BASE_PATHS
        )
        print(f"✓ 配置加载成功")
        print(f"  - Bot ID: {WECOM_BOT_ID[:8]}...")
        print(f"  - WS URL: {WS_URL}")
        print(f"  - DeepSeek API: {DEEPSEEK_BASE_URL}")
        print(f"  - 知识库文件数: {len(KNOWLEDGE_BASE_PATHS)}")
        return True
    except Exception as e:
        print(f"✗ 配置加载失败: {e}")
        return False


def test_knowledge_base():
    """测试知识库模块"""
    print("\n" + "=" * 50)
    print("测试知识库模块...")
    try:
        from knowledge_base import load_knowledge_base
        kb = load_knowledge_base()
        print(f"✓ 知识库加载成功")
        print(f"  - 内容长度: {len(kb.content)} 字符")
        print(f"  - 章节数: {len(kb.sections)}")

        # 测试搜索
        result = kb.search("采购订单")
        print(f"  - 搜索测试(采购订单): {len(result)} 字符")
        return True
    except Exception as e:
        print(f"✗ 知识库测试失败: {e}")
        return False


def test_llm_client():
    """测试 LLM 客户端（需要网络）"""
    print("\n" + "=" * 50)
    print("测试 LLM 客户端...")
    try:
        from llm_client import create_llm_client
        client = create_llm_client()
        print(f"✓ LLM 客户端初始化成功")

        # 测试调用（需要网络）
        print("  - 正在进行实际 API 调用测试...")
        response = client.ask("你好，请介绍一下你自己")
        print(f"  - API 调用成功")
        print(f"  - 回复: {response[:100]}...")
        return True
    except Exception as e:
        print(f"✗ LLM 客户端测试失败: {e}")
        print("  (这可能是因为 API Key 无效或网络问题)")
        return False


def test_bot_module():
    """测试机器人模块（WebSocket 长连接）"""
    print("\n" + "=" * 50)
    print("测试机器人模块...")
    try:
        from bot import WeComBot
        from config import WECOM_BOT_ID, WECOM_SECRET, WS_URL
        bot = WeComBot(WECOM_BOT_ID, WECOM_SECRET, WS_URL)
        print(f"✓ WeComBot 实例创建成功")
        print(f"  - Bot ID: {bot.bot_id[:8]}...")
        print(f"  - WS URL: {bot.ws_url}")
        return True
    except Exception as e:
        print(f"✗ 机器人模块测试失败: {e}")
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 50)
    print("金小石机器人 - 模块测试")
    print("=" * 50)

    results = []

    results.append(("配置模块", test_config()))
    results.append(("知识库模块", test_knowledge_base()))
    results.append(("机器人模块", test_bot_module()))
    results.append(("LLM 客户端", test_llm_client()))

    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {name}: {status}")

    print(f"\n总计: {passed}/{total} 通过")

    if passed == total:
        print("\n🎉 所有测试通过！可以启动服务了。")
        return 0
    else:
        print("\n⚠️ 部分测试失败，请检查配置。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
