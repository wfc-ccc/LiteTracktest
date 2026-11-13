"""权限矩阵（数据驱动）：4 角色 × 3 个敏感接口。

契约：全局异常处理器不改写 HTTP 状态码，权限不足时 HTTP 仍是 200，
body.code = 403（RoleAspect 拦截）。所以断言的是业务码，不是 HTTP 状态码。

矩阵写在 data/permission_matrix.yaml，用例只负责遍历 + DB 复核：
接口说「拒绝了」不算数，库里那行没被动过才算数。
"""

from __future__ import annotations

import allure
import pytest

from utils.config_loader import load_yaml

pytestmark = pytest.mark.api

_MATRIX = load_yaml("permission_matrix.yaml")
_ENDPOINTS = _MATRIX["endpoints"]

# 前置状态 -> conftest 里的造数夹具
_STATE_FIXTURE = {
    "TODO": "todo_task_id",
    "PENDING_REVIEW": "setup_task",
}

# 只比对会被业务改动的列；update_time 之类可能被 MySQL 自动刷新，不参与判断
_WATCHED = (
    "status",
    "assignee_id",
    "submit_hours",
    "submit_desc",
    "latest_audit_result",
    "latest_audit_reason",
)

_CASES = [
    pytest.param(
        row["role"],
        row["account"],
        row["client_fixture"],
        row["expected"][endpoint_key],
        endpoint_key,
        id=f"{row['account']}-{endpoint_key}",
    )
    for row in _MATRIX["matrix"]
    for endpoint_key in _ENDPOINTS
]


def _snapshot(db, task_id: int) -> dict:
    """取任务的业务字段快照，用于判断接口有没有产生副作用。"""
    row = db.fetch_task(task_id)
    assert row is not None, f"任务 {task_id} 不存在"
    return {key: row[key] for key in _WATCHED}


def _materialize(body: dict | None, login, env) -> dict | None:
    """把 YAML 里的账号键占位换成真实用户 ID，例如 assigneeId: dev01。"""
    if not body:
        return None
    payload = dict(body)
    for key, value in payload.items():
        if isinstance(value, str) and value in env["accounts"]:
            payload[key] = login(value)["user"]["id"]
    return payload


def _assert_no_side_effect(db, task_id: int, before: dict, role: str, endpoint_key: str) -> None:
    """越权请求的底线：库里那行必须原封不动。"""
    after = _snapshot(db, task_id)
    assert after == before, f"{role} 越权调用 {endpoint_key} 不该改动任务: before={before}, after={after}"


@allure.feature("任务管理")
@allure.story("权限矩阵")
class TestTaskPermissionMatrix:
    @allure.title("{role} 调用 {endpoint_key} 接口：期望业务码 {expected_code}")
    @pytest.mark.parametrize(
        "role,account_key,client_fixture,expected_code,endpoint_key", _CASES
    )
    def test_permission_matrix(
        self,
        request,
        env,
        login,
        db,
        role,
        account_key,
        client_fixture,
        expected_code,
        endpoint_key,
    ):
        spec = _ENDPOINTS[endpoint_key]
        task_id = request.getfixturevalue(_STATE_FIXTURE[spec["pre_state"]])
        client = request.getfixturevalue(client_fixture)
        payload = _materialize(spec.get("body"), login, env)
        before = _snapshot(db, task_id)

        with allure.step(
            f"{role}（{account_key}）调用 {spec['method']} {spec['path']}"
            f"，任务 {task_id} 前置状态 {spec['pre_state']}（{spec['label']}）"
        ):
            url = spec["path"].format(task_id=task_id)
            if payload is None:
                response = client.request(spec["method"].upper(), url)
            else:
                response = client.request(spec["method"].upper(), url, json=payload)

        with allure.step("断言 HTTP 200，且业务码与矩阵一致"):
            assert response.status_code == 200, response.text
            body = response.json()
            allure.attach(
                response.text,
                name=f"{account_key}-{endpoint_key}-response",
                attachment_type=allure.attachment_type.JSON,
            )
            assert "code" in body, body
            assert body["code"] == expected_code, (
                f"{role} 调 {endpoint_key} 期望业务码 {expected_code}，实际 {body}"
            )

        with allure.step("DB 复核：接口结论与落库效果一致"):
            if expected_code != 200:
                _assert_no_side_effect(db, task_id, before, role, endpoint_key)
            elif endpoint_key == "accept":
                assert _snapshot(db, task_id)["status"] == "DOING", db.fetch_task(task_id)
            elif endpoint_key == "audit":
                after = _snapshot(db, task_id)
                assert after["status"] == "DONE", after
                assert after["latest_audit_result"] == "PASS", after
            elif endpoint_key == "assign":
                expected_assignee = login("dev01")["user"]["id"]
                assert _snapshot(db, task_id)["assignee_id"] == expected_assignee, db.fetch_task(task_id)
