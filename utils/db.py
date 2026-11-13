"""MySQL 访问封装，用于任务表（task）与缺陷表（bug）的双重断言。

思路是「接口验结果、数据库验落库」：先用 TaskApi / BugApi 拿到业务响应，
再用本模块直连库核对同一条记录，两边互为印证，避免只信接口返回。
连接参数取自 config/env.yaml 当前环境的 ``db`` 节点，用例通过 conftest 的 ``db`` 夹具使用。
"""

from __future__ import annotations

from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor


class DBClient:
    """pymysql 的薄封装：查询统一返回字典行，写操作显式提交，连接随用随关。"""

    def __init__(self, config: dict):
        self._config = {
            "host": config.get("host", "localhost"),
            "port": int(config.get("port", 3306)),
            "user": config["user"],
            "password": str(config["password"]),
            "database": config["database"],
            "charset": config.get("charset", "utf8mb4"),
            "cursorclass": DictCursor,
        }

    @classmethod
    def from_env(cls, env: dict) -> "DBClient":
        """从 load_env() 的返回值构造，缺少 db 节点时尽早报错。"""
        db_config = env.get("db")
        if not db_config:
            raise KeyError(f"环境 {env.get('name')!r} 未配置 db 节点，无法做数据库断言")
        return cls(db_config)

    @contextmanager
    def connect(self):
        conn = pymysql.connect(**self._config)
        try:
            yield conn
        finally:
            conn.close()

    def query(self, sql: str, params: tuple | list | None = None) -> list[dict]:
        """执行 SELECT，返回字典行列表；无结果时返回空列表。"""
        with self.connect() as conn, conn.cursor() as cursor:
            cursor.execute(sql, params or ())
            return list(cursor.fetchall())

    def query_one(self, sql: str, params: tuple | list | None = None) -> dict | None:
        """执行 SELECT 并取第一条，没有则返回 None。"""
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: tuple | list | None = None) -> int:
        """执行写操作并提交，返回受影响行数。"""
        with self.connect() as conn, conn.cursor() as cursor:
            affected = cursor.execute(sql, params or ())
            conn.commit()
            return affected

    def fetch_task(self, task_id: int) -> dict | None:
        """按主键取任务行，字段与后端 task 表一致。"""
        return self.query_one("SELECT * FROM task WHERE id = %s", (task_id,))

    def fetch_bug(self, bug_id: int) -> dict | None:
        """按主键取缺陷行，字段与后端 bug 表一致。"""
        return self.query_one("SELECT * FROM bug WHERE id = %s", (bug_id,))
