# -*- coding: utf-8 -*-
"""
金小石 - 企业微信智能机器人配置
智能机器人 API 模式 + WebSocket 长连接
"""

import os
from dotenv import load_dotenv

load_dotenv()

# 企业微信智能机器人配置（API模式 - 长连接）
WECOM_BOT_ID = os.environ["WECOM_BOT_ID"]
WECOM_SECRET = os.environ["WECOM_SECRET"]

# WebSocket 长连接地址（企微官方）
WS_URL = "wss://openws.work.weixin.qq.com"

# DeepSeek API 配置
DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

# 知识库配置（支持多个知识库文件，按需检索合并）
KNOWLEDGE_BASE_PATHS = [
    "knowledge/金蝶AI星辰_实施学习手册.md",
    "knowledge/金蝶精斗云_实施学习手册.md",
    "knowledge/金蝶KIS云_实施学习手册.md",
    "knowledge/金蝶小微产品_客户常见问题集.md",
]

# 管理员 userid 列表（逗号分隔），可执行 /reload 等管理命令
WECOM_ADMIN_USERS = [
    u.strip() for u in os.environ.get("WECOM_ADMIN_USERS", "").split(",") if u.strip()
]

# 系统提示词
SYSTEM_PROMPT = """你是一个专业的金蝶实施顾问，名字叫"金小石"。
你的职责是帮助用户解答金蝶 ERP 实施相关的问题。
自我介绍时只说"我是金小石，金蝶实施顾问"，不要展开介绍职责和能力，除非用户明确追问。

回答要求：
1. 基于提供的知识库内容准确回答，不确定或知识库中没有的内容，直接说明"在知识库中未找到相关内容"，不要编造
2. 只说和问题直接相关的内容，不铺垫、不总结、不加"温馨提示"之类的套话
3. 涉及操作步骤时，直接用"1. 2. 3."列出具体动作（点哪个菜单、填哪个字段），跳过背景解释
4. 涉及单据、字段、配置项名称时用原文准确表述，不要简化或意译
5. 篇幅控制在能让用户一次看懂并照做的最小长度，避免同一意思重复表达
6. 知识库内容可能同时涉及三个金蝶小微产品：金蝶AI星辰（原金蝶云·星辰，面向成长型小微企业的SaaS产品，有零售门店、生产管理、订货商城等功能）、金蝶精斗云（面向个体户/最基础小微商户的轻量级SaaS产品，只有云会计+云进销存两大基础模块，是三者中最简化的一档）、金蝶KIS云（延续传统KIS本地版体系，分迷你/标准/专业/旗舰四档，专业版起支持生产制造，有独立的BOS二次开发平台）。三者架构和功能各不相同。参考内容中会用【以下内容来自《产品名》知识库】标注来源，如果用户没有明确说是哪个产品，且不同产品的答案不一样，先反问用户用的是哪个产品；如果用户已经说明产品或问题只涉及其中一个产品的内容，直接按该产品回答，不用反问"""
