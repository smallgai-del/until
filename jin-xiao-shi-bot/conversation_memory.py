# -*- coding: utf-8 -*-
"""
对话上下文模块 - 按 chat_id 维护最近 N 轮对话历史，支持超时自动清空
"""

import threading
import time
from collections import deque

MAX_TURNS = 5          # 每个会话最多保留的问答轮数
IDLE_TIMEOUT = 1800     # 会话空闲超时（秒），超过则清空历史


class ConversationMemory:
    """线程安全的会话历史管理器"""

    def __init__(self, max_turns: int = MAX_TURNS, idle_timeout: int = IDLE_TIMEOUT):
        self.max_turns = max_turns
        self.idle_timeout = idle_timeout
        self._store = {}  # chat_id -> {"messages": deque, "last_active": ts}
        self._lock = threading.Lock()

    def get_history(self, chat_id: str) -> list:
        """获取指定会话的历史消息（用于拼接进 LLM 请求）"""
        with self._lock:
            entry = self._store.get(chat_id)
            if not entry:
                return []
            if time.time() - entry["last_active"] > self.idle_timeout:
                del self._store[chat_id]
                return []
            return list(entry["messages"])

    def append(self, chat_id: str, question: str, answer: str):
        """记录一轮问答"""
        with self._lock:
            entry = self._store.get(chat_id)
            if not entry or time.time() - entry["last_active"] > self.idle_timeout:
                entry = {"messages": deque(maxlen=self.max_turns * 2), "last_active": time.time()}
                self._store[chat_id] = entry

            entry["messages"].append({"role": "user", "content": question})
            entry["messages"].append({"role": "assistant", "content": answer})
            entry["last_active"] = time.time()

    def clear(self, chat_id: str):
        """清空指定会话的历史"""
        with self._lock:
            self._store.pop(chat_id, None)


_memory = ConversationMemory()


def get_history(chat_id: str) -> list:
    return _memory.get_history(chat_id)


def append(chat_id: str, question: str, answer: str):
    _memory.append(chat_id, question, answer)


def clear(chat_id: str):
    _memory.clear(chat_id)
