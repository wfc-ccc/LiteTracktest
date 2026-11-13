"""提交接口的参数边界校验：脏参数必须被拒，并且不能落库。

submitHours 声明了 minimum=0（负数非法）、submitDesc 声明了 minLength=1（空/缺省非法），
校验异常同样走全局异常处理器，HTTP 可能是 200（业务码非 200）也可能是 4xx，
所以判定口径统一为「不被放行」+「错误提示指向问题字段」+「DB 无脏数据」。
"""

from __future__ import annotations

import allure
import pytest

from api.task_api import TaskApi

pytestmark = pytest.mark.api

# 正常提交的基线，用例在它上面做加减
_BASE_SUBMIT = {
    "submitHours": 1.0,
    "submitDesc": "参数边界用例的基线提交说明",
    "submitAttachments": "",
}

# 覆盖值里出现这个哨兵，表示「整个字段不传」
_DROP = object()

# 提示语容错：不同实现可能报中文字段名，也可能报 Java 字段名
_HOURS_KEYWORDS = ("工时", "hours", "Hours", "submitHours")
_DESC_KEYWORDS = ("提交说明", "submitDesc", "可测版本")

_WATCHED = ("status", "submit_hours", "submit_desc", "submit_attachments")

_CASES = [
    pytest.param("工时传负数 -1", {"submitHours": -1}, _HOURS_KEYWORDS, id="hours-negative"),
    pytest.param("工时传空字符串", {"submitHours": ""}, _HOURS_KEYWORDS, id="hours-blank"),
    pytest.param("不传 submitDesc", {"submitDesc": _DROP}, _DESC_KEYWORDS, id="desc-missing"),
]


def _build_payload(overrides: dict) -> dict:
    payload = dict(_BASE_SUBMIT)
    for key, value in overrides.items():
        if value is _DROP:
            payload.pop(key, None)
        else:
            payload[key] = value
    return payload


def _json(response) -> dict:
    """校验失败时响应体可能不是 JSON，统一兜底成空字典。"""
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _message(body: dict) -> str:
    for key in ("message", "msg", "error"):
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _snapshot(db, task_id: int) -> dict:
    row = db.fetch_task(task_id)
    assert row is not None, f"任务 {task_id} 不存在"
    return {key: row[key] for key in _WATCHED}


@pytest.fixture
def doing_task_id(todo_task_id, task_api, pm_token) -> int:
    """TODO -> DOING，交给用例做提交参数校验；清理复用 todo_task_id 的 teardown。"""
    TaskApi.raise_if_business_failed(
        task_api.accept(pm_token, todo_task_id),
        "造 DOING 任务：接受任务",
    )
    yield todo_task_id


@allure.feature("任务管理")
@allure.story("参数边界校验")
class TestTaskSubmitValidation:
    @allure.title("提交接口脏参数拦截：{label}")
    @pytest.mark.parametrize("label,overrides,keywords", _CASES)
    def test_submit_rejects_invalid_params(
        self, doing_task_id, dev_client, db, label, overrides, keywords
    ):
        task_id = doing_task_id

        with allure.step("前置：任务处于 DOING，具备提交资格"):
            before = _snapshot(db, task_id)
            assert before["status"] == "DOING", before

        payload = _build_payload(overrides)
        with allure.step(f"DEV 提交脏参数（{label}）：{payload}"):
            response = dev_client.patch(f"/api/tasks/{task_id}/submit", json=payload)

        with allure.step("断言请求被拦截"):
            body = _json(response)
            allure.attach(
                response.text or "",
                name="submit-invalid-response",
                attachment_type=allure.attachment_type.TEXT,
            )
            assert response.status_code != 200 or body.get("code") != 200, (
                f"脏参数不该通过: http={response.status_code}, body={body}"
            )

        with allure.step("断言错误提示指向问题字段"):
            message = _message(body)
            assert message, f"被拒但缺少错误提示: http={response.status_code}, body={body}"
            assert any(keyword in message for keyword in keywords), (
                f"错误提示未指向问题字段，期望含 {keywords} 之一，实际：{message}"
            )

        with allure.step("DB 断言：没有写入脏数据，状态与提交字段保持原样"):
            assert _snapshot(db, task_id) == before, f"脏参数不该落库: {db.fetch_task(task_id)}"
