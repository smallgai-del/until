# -*- coding: utf-8 -*-
"""
金小石 - 企业微信智能机器人
基于 WebSocket 长连接（智能机器人 API 模式）
只需 Bot ID + Secret，无需公网 IP / 域名
"""

import os
import sys
import json
import uuid
import time
import logging
import threading
import websocket

from qa_logger import init_db, log_qa
from conversation_memory import get_history, append as append_history

init_db()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# 导入配置
from config import (
    WECOM_BOT_ID, WECOM_SECRET, WS_URL,
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    SYSTEM_PROMPT, KNOWLEDGE_BASE_PATHS, WECOM_ADMIN_USERS
)

# 全局实例（懒加载）
_knowledge_base = None
_llm_client = None


def get_knowledge_base():
    """获取知识库实例（懒加载，聚合多个知识库文件）"""
    global _knowledge_base
    if _knowledge_base is None:
        from knowledge_base import load_knowledge_bases
        _knowledge_base = load_knowledge_bases(KNOWLEDGE_BASE_PATHS)
        logger.info(f"知识库加载完成: {_knowledge_base.get_source_labels()}")
    return _knowledge_base


def reload_knowledge_base():
    """强制重新加载知识库文件（用于管理员热重载命令）"""
    global _knowledge_base
    from knowledge_base import load_knowledge_bases
    _knowledge_base = load_knowledge_bases(KNOWLEDGE_BASE_PATHS)
    logger.info(f"知识库已热重载: {_knowledge_base.get_source_labels()}")
    return _knowledge_base


def get_llm_client():
    """获取 LLM 客户端（懒加载）"""
    global _llm_client
    if _llm_client is None:
        from llm_client import create_llm_client
        _llm_client = create_llm_client()
        logger.info("DeepSeek LLM 客户端初始化完成")
    return _llm_client


class WeComBot:
    """企业微信智能机器人 - WebSocket 长连接模式"""

    def __init__(self, bot_id: str, secret: str, ws_url: str = WS_URL):
        self.bot_id = bot_id
        self.secret = secret
        self.ws_url = ws_url
        self.ws = None
        self.authenticated = False
        self._heartbeat_thread = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # WebSocket 回调
    # ------------------------------------------------------------------

    def _on_open(self, ws):
        """连接建立 → 发送订阅鉴权"""
        logger.info("WebSocket 连接已建立，正在鉴权...")
        subscribe_msg = {
            "cmd": "aibot_subscribe",
            "headers": {"req_id": str(uuid.uuid4())},
            "body": {
                "bot_id": self.bot_id,
                "secret": self.secret
            }
        }
        ws.send(json.dumps(subscribe_msg, ensure_ascii=False))

    def _on_message(self, ws, message):
        """收到服务端消息"""
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            logger.warning(f"收到非 JSON 消息: {message[:200]}")
            return

        cmd = data.get("cmd")

        # 订阅成功
        if data.get("errcode") == 0 and not cmd:
            if not self.authenticated:
                self.authenticated = True
                logger.info("✅ 鉴权成功！机器人已上线")
                self._start_heartbeat()
            return

        if cmd == "aibot_msg_callback":
            # 用户消息回调
            threading.Thread(
                target=self._handle_msg_callback,
                args=(data,),
                daemon=True
            ).start()

        elif cmd == "aibot_event_callback":
            # 事件回调（进入聊天界面、点赞等）
            event_type = data.get("body", {}).get("event_type", "")
            logger.info(f"收到事件: {event_type}")

        elif cmd == "pong":
            pass  # 心跳响应

    def _on_error(self, ws, error):
        logger.error(f"WebSocket 错误: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        logger.warning(f"WebSocket 连接关闭 (code={close_status_code}, msg={close_msg})")
        self.authenticated = False
        if not self._stop_event.is_set():
            threading.Thread(target=self._reconnect, daemon=True).start()

    # ------------------------------------------------------------------
    # 消息处理
    # ------------------------------------------------------------------

    def _handle_msg_callback(self, data: dict):
        """处理用户消息回调"""
        body = data.get("body", {})
        headers = data.get("headers", {})
        req_id = headers.get("req_id", "")

        msg_type = body.get("msgtype", "")
        chat_type = body.get("chattype", "single")
        from_user = body.get("from", {}).get("userid", "unknown")
        msg_id = body.get("msgid", "")

        # 确定 chat_id
        if chat_type == "group":
            chat_id = body.get("chatid", "")
        else:
            chat_id = from_user

        logger.info(f"收到消息 [{chat_type}] from={from_user} type={msg_type}")

        # 只处理文本消息
        if msg_type != "text":
            self._reply_stream_simple(req_id, chat_id, chat_type, "暂时只支持文本消息哦~")
            return

        content = body.get("text", {}).get("content", "").strip()
        if not content:
            return

        # 群聊去掉 @机器人 部分
        if chat_type == "group":
            content = self._clean_at_content(content)

        if not content:
            return

        # 管理员命令处理
        if content in ("/reload", "reload") and from_user in WECOM_ADMIN_USERS:
            self._handle_reload_command(req_id, chat_id, chat_type)
            return

        logger.info(f"问题: {content}")

        start_time = time.time()

        # 知识库检索
        kb = get_knowledge_base()
        context = kb.search(content)

        # 构建 prompt
        if context:
            question = (
                f"基于以下参考资料回答用户问题。如果资料中没有相关信息，请说明。\n\n"
                f"参考资料：\n{context}\n\n"
                f"用户问题：{content}"
            )
        else:
            suggestions = kb.suggest_sections(content)
            suggestion_hint = (
                f"（未在知识库中检索到直接相关的内容，可能相关的章节：{'、'.join(suggestions)}）"
                if suggestions else ""
            )
            question = (
                f"知识库中未找到与该问题直接相关的内容，请基于你的通用知识谨慎回答，"
                f"并明确提醒用户这不是知识库中的内容。{suggestion_hint}\n\n"
                f"用户问题：{content}"
            )

        # 调用 LLM（携带历史对话，支持多轮追问）
        llm = get_llm_client()
        history = get_history(chat_id)
        reply = llm.ask(question, history=history)

        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(f"回复 ({len(reply)} 字, {elapsed_ms}ms): {reply[:100]}...")

        # 历史中保留原始问题（不含知识库拼接内容），避免上下文越滚越大
        append_history(chat_id, content, reply)

        try:
            log_qa(chat_id, chat_type, from_user, content, bool(context), reply, elapsed_ms)
        except Exception as e:
            logger.warning(f"问答日志写入失败: {e}")

        # 一次性回复（单条消息，不分块）
        self._reply_stream_simple(req_id, chat_id, chat_type, reply)

    def _handle_reload_command(self, req_id: str, chat_id: str, chat_type: str):
        """管理员热重载知识库"""
        try:
            kb = reload_knowledge_base()
            labels = "、".join(kb.get_source_labels())
            msg = f"✅ 知识库已重新加载，共 {len(kb.knowledge_bases)} 个知识库（{labels}），{len(kb.sections)} 个章节。"
            logger.info(f"管理员触发知识库热重载，来自 chat_id={chat_id}")
        except Exception as e:
            msg = f"❌ 知识库重新加载失败: {e}"
            logger.error(f"知识库热重载失败: {e}")
        self._reply_stream_simple(req_id, chat_id, chat_type, msg)

    def _clean_at_content(self, content: str) -> str:
        """去掉群聊中 @机器人 的内容"""
        import re
        content = re.sub(r'@\u91d1\u5c0f\u77f3\s*', '', content).strip()
        return content

    # ------------------------------------------------------------------
    # 回复方式
    # ------------------------------------------------------------------

    def _reply_stream_simple(self, req_id: str, chat_id: str, chat_type: str, content: str):
        """一次性回复（单条消息，不分块）"""
        chat_type_int = 1 if chat_type == "single" else 2
        reply = {
            "cmd": "aibot_send_msg",
            "headers": {"req_id": req_id},
            "body": {
                "chatid": chat_id,
                "chat_type": chat_type_int,
                "msgtype": "markdown",
                "stream_id": str(uuid.uuid4()),
                "stream_finish": True,
                "markdown": {"content": content}
            }
        }
        try:
            self.ws.send(json.dumps(reply, ensure_ascii=False))
        except Exception as e:
            logger.error(f"回复发送失败: {e}")

    def send_message(self, chat_id: str, content: str, chat_type: str = "single"):
        """主动推送消息"""
        chat_type_int = 1 if chat_type == "single" else 2
        msg = {
            "cmd": "aibot_send_msg",
            "headers": {"req_id": str(uuid.uuid4())},
            "body": {
                "chatid": chat_id,
                "chat_type": chat_type_int,
                "msgtype": "markdown",
                "markdown": {"content": content}
            }
        }
        try:
            self.ws.send(json.dumps(msg, ensure_ascii=False))
            logger.info(f"主动消息已发送: {chat_id}")
        except Exception as e:
            logger.error(f"主动消息发送失败: {e}")

    # ------------------------------------------------------------------
    # 心跳 & 重连
    # ------------------------------------------------------------------

    def _start_heartbeat(self):
        """启动心跳线程（每 20 秒 ping）"""
        def heartbeat():
            while not self._stop_event.is_set():
                self._stop_event.wait(20)
                if self._stop_event.is_set():
                    break
                try:
                    if self.ws and self.authenticated:
                        ping = {
                            "cmd": "ping",
                            "headers": {"req_id": str(uuid.uuid4())}
                        }
                        self.ws.send(json.dumps(ping))
                except Exception as e:
                    logger.warning(f"心跳发送失败: {e}")

        self._heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
        self._heartbeat_thread.start()
        logger.info("心跳线程已启动")

    def _reconnect(self):
        """断线重连（指数退避）"""
        retry = 0
        max_delay = 60

        while not self._stop_event.is_set():
            retry += 1
            delay = min(2 ** retry, max_delay)
            logger.info(f"第 {retry} 次重连，{delay}秒后尝试...")
            self._stop_event.wait(delay)

            if self._stop_event.is_set():
                break

            try:
                self._connect()
                logger.info("重连成功")
                return
            except Exception as e:
                logger.error(f"重连失败: {e}")

    # ------------------------------------------------------------------
    # 启动 & 停止
    # ------------------------------------------------------------------

    def _connect(self):
        """建立 WebSocket 连接"""
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        self.ws.run_forever()

    def start(self):
        """启动机器人"""
        logger.info("=" * 50)
        logger.info("🤖 金小石 - 企业微信智能机器人")
        logger.info("=" * 50)
        logger.info(f"Bot ID : {self.bot_id}")
        logger.info(f"WS URL : {self.ws_url}")
        logger.info(f"LLM    : DeepSeek ({DEEPSEEK_MODEL})")
        logger.info("=" * 50)
        self._connect()

    def stop(self):
        """停止机器人"""
        logger.info("正在停止...")
        self._stop_event.set()
        if self.ws:
            self.ws.close()


# ------------------------------------------------------------------
# 入口
# ------------------------------------------------------------------

bot_instance = None


def main():
    """主函数"""
    global bot_instance
    bot_instance = WeComBot(WECOM_BOT_ID, WECOM_SECRET)

    def signal_handler(sig, frame):
        logger.info("收到退出信号")
        if bot_instance:
            bot_instance.stop()
        sys.exit(0)

    import signal
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    bot_instance.start()


if __name__ == "__main__":
    main()
