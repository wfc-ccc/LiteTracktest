"""读取 config/env.yaml，并按 active 或 LITETRACK_ENV 选出当前环境。"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "config" / "env.yaml"
DATA_DIR = ROOT / "data"


@lru_cache(maxsize=1)
def load_env(path: str | None = None) -> dict:
    """返回当前环境配置（已合并环境名）。

    Pytest 中不要在用例里直接打开文件，使用 conftest.py 的 ``env`` fixture。
    """
    env_path = Path(path) if path else ENV_FILE
    with env_path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    active = os.getenv("LITETRACK_ENV", raw.get("active", "dev"))
    if active not in raw or not isinstance(raw[active], dict):
        known = [key for key, value in raw.items() if isinstance(value, dict)]
        raise KeyError(f"env.yaml 中不存在环境 {active!r}，可选：{known}")

    current = dict(raw[active])
    current["name"] = active
    accounts = current.get("accounts") or {}
    for key in ("admin", "pm01", "dev01", "qa01"):
        if key not in accounts:
            raise KeyError(f"环境 {active} 缺少账号 {key}")
    return current


def load_yaml(name: str) -> dict:
    """读取 data/ 下的 YAML 测试数据。"""
    path = DATA_DIR / name
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}
