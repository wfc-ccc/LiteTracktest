"""状态机逆向拦截：跳过前置状态直接调接口，必须被拒且一行都不许改。

轻舟的任务状态机是 TODO -> DOING -> PENDING_REVIEW -> DONE。
这里刻意绕开顺序，直接拿 DONE 的任务去「接受」、拿 TODO 的任务去「审核」，
验证两条底线：
1. 接口层面被拦（HTTP 200 但 body.code != 200，全局异常处理器不改写状态码）；
2. 数据库层面零副作用，状态与审核痕迹保持原样。
"""

from __future__ import annotations

import allure
import pytest

from api.task_api import TaskApi

pytestmark = pytest.mark.api

# 只比对会被状态机改动的列，避免 update_time 之类的干扰
_WATCHED = (
    "status",
    "submit_hours",
    "submit_desc",
    "latest_audit_result",
    "latest_audit_reason",
    "latest_audit_time",
)


def _snapshot(db, task_id: int) -> dict:
    row = db.fetch_task(task_id)
    assert row is not None, f"任务 {task_id} 不存在"
    return {key: row[key] for key in _WATCHED}


@pytest.fixture
def done_task_id(setup_task, task_api, pm_token, audit_payload) -> int:
    """把 setup_task 造出的待审核任务审到 DONE；清理复用 setup_task 的 teardown。"""
    TaskApi.raise_if_business_failed(
        task_api.audit(
            pm_token,
            setup_task,
            audit_payload["auditResult"],
            audit_payload["auditReason"],
        ),
        "造 DONE 任务：PM 审核通过",
    )
    yield setup_task


@allure.feature("任务管理")
@allure.story("状态机防篡改")
class TestTaskStateMachine:
    @allure.title("对 DONE 任务调接受接口：HTTP 200 但业务失败，DB 状态仍是 DONE")
    def test_accept_on_done_is_rejected(self, done_task_id, dev_client, db):
        task_id = done_task_id

        with allure.step("前置：任务已处于终态 DONE"):
            before = _snapshot(db, task_id)
            assert before["status"] == "DONE", before

        with allure.step("DEV（任务负责人）对 DONE 任务调用 PATCH /api/tasks/{id}/accept"):
            response = dev_client.patch(f"/api/tasks/{task_id}/accept")

        with allure.step("断言 HTTP 200，但业务码不是成功（状态机拦截）"):
            assert response.status_code == 200, response.text
            body = response.json()
            allure.attach(
                response.text,
                name="accept-on-done-response",
                attachment_type=allure.attachment_type.JSON,
            )
            assert body.get("code") != 200, f"DONE 任务不该被接受: {body}"

        with allure.step("DB 断言：状态仍为 DONE，未产生任何副作用"):
            assert _snapshot(db, task_id) == before, f"被拒的请求不该改动任务: {db.fetch_task(task_id)}"

    @allure.title("对 TODO 任务调审核接口：被拦截，DB 状态仍是 TODO 且无审核痕迹")
    def test_audit_on_todo_is_rejected(self, todo_task_id, pm_client, db):
        task_id = todo_task_id

        with allure.step("前置：任务停在初始态 TODO，尚未被接受/提交"):
            before = _snapshot(db, task_id)
            assert before["status"] == "TODO", before

        with allure.step("PM（有审核权限）对 TODO 任务调用 PATCH /api/tasks/{id}/audit"):
            response = pm_client.patch(
                f"/api/tasks/{task_id}/audit",
                json={"auditResult": "PASS", "auditReason": "状态机用例： TODO 不该能直接审核"},
            )

        with allure.step("断言 HTTP 200，但业务码不是成功（状态机拦截）"):
            assert response.status_code == 200, response.text
            body = response.json()
            allure.attach(
                response.text,
                name="audit-on-todo-response",
                attachment_type=allure.attachment_type.JSON,
            )
            assert body.get("code") != 200, f"TODO 任务不该能直接审核: {body}"

        with allure.step("DB 断言：状态仍是 TODO，且没有写入审核结论"):
            after = _snapshot(db, task_id)
            assert after == before, f"被拒的审核不该改动任务: {db.fetch_task(task_id)}"
            assert after["latest_audit_result"] is None, after
