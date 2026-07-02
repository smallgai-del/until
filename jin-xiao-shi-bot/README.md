# 金小石 - 企业微信智能机器人

金石软件专属的金蝶 ERP 实施知识库问答机器人，接入企业微信智能机器人 API 模式（WebSocket 长连接）。

## 技术栈

- **接入方式**: 企业微信智能机器人 API 模式 + WebSocket 长连接
- **大模型**: DeepSeek (deepseek-chat)
- **知识库**: 金蝶云星空旗舰版 + 金蝶K3 WISE 实施学习手册（多知识库，按内容自动匹配来源）
- **语言**: Python 3.8+

## 优势

- ✅ 无需公网 IP / 域名
- ✅ 无需配置 Nginx / HTTPS
- ✅ 内网即可运行
- ✅ 只需 Bot ID + Secret

## 部署步骤

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 检查配置

编辑 `config.py`，确认以下信息正确：

```python
WECOM_BOT_ID = "你的Bot ID"
WECOM_SECRET = "你的Secret"
DEEPSEEK_API_KEY = "你的DeepSeek API Key"
```

### 3. 启动机器人

```bash
python bot.py
```

看到以下日志表示启动成功：

```
✅ 鉴权成功！机器人已上线
心跳线程已启动
```

### 4. 测试

- **单聊**: 在企业微信通讯录找到"金小石"，直接发消息
- **群聊**: 把机器人拉进群，@金小石 提问

## 文件结构

```
jin-xiao-shi-bot/
├── bot.py              # 主服务（WebSocket 长连接）
├── config.py           # 配置文件
├── knowledge_base.py   # 知识库检索模块（支持多知识库文件聚合检索）
├── llm_client.py       # DeepSeek API 客户端
├── requirements.txt    # Python 依赖
├── README.md           # 本文件
└── knowledge/
    ├── 金蝶星空旗舰版_实施学习手册.md  # 云星空旗舰版知识库
    └── 金蝶K3WISE_实施学习手册.md      # K3 WISE知识库
```

新增知识库文件时，把路径加进 `config.py` 的 `KNOWLEDGE_BASE_PATHS` 列表即可，机器人会自动聚合检索并标注内容来源。
