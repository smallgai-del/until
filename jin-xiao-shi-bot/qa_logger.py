# -*- coding: utf-8 -*-
"""
问答日志模块 - 记录问答历史到 SQLite，便于分析知识库命中情况
"""

import sqlite3
from contextlib import contextmanager

DB_PATH = "qa_log.db"


@contextmanager
def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: str = None):
    """初始化数据库表结构"""
    global DB_PATH
    if db_path:
        DB_PATH = db_path
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS qa_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                chat_id TEXT,
                chat_type TEXT,
                from_user TEXT,
                question TEXT,
                kb_hit INTEGER,
                answer TEXT,
                elapsed_ms INTEGER
            )
        """)
        conn.commit()


def log_qa(chat_id: str, chat_type: str, from_user: str,
           question: str, kb_hit: bool, answer: str, elapsed_ms: int):
    """记录一条问答日志"""
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO qa_log
               (chat_id, chat_type, from_user, question, kb_hit, answer, elapsed_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (chat_id, chat_type, from_user, question, int(kb_hit), answer, elapsed_ms)
        )
        conn.commit()


def get_unmatched_questions(limit: int = 50):
    """获取知识库未命中的问题列表，用于补充知识库"""
    with _get_conn() as conn:
        cursor = conn.execute(
            """SELECT question, COUNT(*) as cnt, MAX(created_at) as last_seen
               FROM qa_log WHERE kb_hit = 0
               GROUP BY question ORDER BY cnt DESC, last_seen DESC LIMIT ?""",
            (limit,)
        )
        return cursor.fetchall()
