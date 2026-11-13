"""启动自检：确认后端（8080）与前端（5173）都还活着。

地址取自 config/env.yaml 当前环境的 ``api_base_url`` 与 ``web_base_url``，
切换环境仍是 ``active`` 或 ``LITETRACK_ENV``。任一服务不可用返回非 0 退出码，
方便在本地跑测试前、或 Jenkins 阶段里前置拦一道。

用法：
    python health_check.py
    python health_check.py --timeout 3
"""

from __future__ import annotations

import argparse
import sys

import requests

from utils.config_loader import load_env


def check(url: str, timeout: float = 5.0) -> tuple[bool, str]:
    """探活单个地址。连不上或整体不可用判为失败，5xx 也算服务异常。"""
    try:
        response = requests.get(url, timeout=timeout)
    except requests.RequestException as exc:
        return False, exc.__class__.__name__
    ok = response.status_code < 500
    return ok, f"HTTP {response.status_code}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LiteTrack 环境存活自检")
    parser.add_argument("--timeout", type=float, default=5.0, help="单次请求超时秒数")
    args = parser.parse_args(argv)

    env = load_env()
    targets = {
        "后端 api": env["api_base_url"],
        "前端 web": env["web_base_url"],
    }

    alive = True
    for name, url in targets.items():
        ok, detail = check(url, args.timeout)
        # 用固定宽度对齐，等长更利于流水线日志阅读
        flag = "OK  " if ok else "FAIL"
        print(f"[{flag}] {name}  {url}  ->  {detail}")
        alive = alive and ok

    print(f"环境自检{'通过' if alive else '失败：服务未就绪'}（env={env['name']}）")
    return 0 if alive else 1


if __name__ == "__main__":
    sys.exit(main())
