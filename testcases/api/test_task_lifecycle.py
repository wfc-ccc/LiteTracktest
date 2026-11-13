"""任务全生命周期：PM 建单 → DEV 接受 → DEV 提交 → PM 审核通过。

每一步都用 utils/db.py 直连库做双重断言：接口只保证「响应成功」，落库才算数。
状态机：TODO -> DOING -> PENDING_REVIEW -> DONE。

工时容错：submitHours 故意传带前后空格的字符串，验证后端 WorkHourDeserializer 去空格后正常解析，
并且 DB 里 submit_hours 按数值正常存储。
"""

from __future__ import annotations

import uuid

import allure
import pytest

from api.task_api import TaskApi

pytestmark = pytest.mark.api

# 带前后空格的工时，后端应去空格解析为 8.5
RAW_SUBMIT_HOURS = " 8.5 "
EXPECTED_SUBMIT_HOURS = 8.5


@pytest.fixture
def lifecycle_task_id(task_api, pm_client, login, project_id) -> int:
    """PM 创建任务并指派给 DEV，交出 task_id；用例结束用 PM 身份删除。"""
    assignee_id = login("dev01")["user"]["id"]
    title = f"auto-lifecycle-{uuid.uuid4().hex[:12]}"

    created = pm_client.post("/api/tasks", json={
        "projectId": project_id,
        "title": title,
        "description": "任务全生命周期用例造数，用例结束会删除",
        "priority": "LOW",
        "assigneeId": assignee_id,
    })
    TaskApi.raise_if_business_failed(created, "PM 创建任务")

    # 创建接口返回 Result<Void>，没有 taskId，按唯一标题回查
    task_id = task_api.find_id_by_title(pm_client.token, title, project_id)

    yield task_id

    deleted = pm_client.delete(f"/api/tasks/{task_id}")
    body = deleted.json()
    assert deleted.status_code == 200 and body.get("code") in (200, 404), (
        f"清理任务 {task_id} 失败: http={deleted.status_code}, body={body}"
    )


@allure.feature("任务管理")
@allure.story("全生命周期")
class TestTaskLifecycle:
    @allure.title("PM 建单 → DEV 接受 → DEV 提交(工时去空格) → PM 审核通过，全程 DB 双重断言")
    def test_full_lifecycle(
        self, lifecycle_task_id, task_api, db, pm_client, dev_client, audit_payload
    ):
        task_id = lifecycle_task_id

        with allure.step("建单后：DB 初始状态应为 TODO"):
            row = db.fetch_task(task_id)
            assert row is not None, f"任务 {task_id} 未落库"
            assert row["status"] == "TODO", row

        with allure.step("DEV 调用 PATCH /api/tasks/{id}/accept 接受任务"):
            response = dev_client.patch(f"/api/tasks/{task_id}/accept")
            assert response.status_code == 200, response.text
            TaskApi.raise_if_business_failed(response, "DEV 接受任务")
        with allure.step("DB 断言：状态已变更为 DOING"):
            row = db.fetch_task(task_id)
            assert row["status"] == "DOING", row

        with allure.step(f'DEV 提交，submitHours 故意传 "{RAW_SUBMIT_HOURS}"，验证工时去空格'):
            response = dev_client.patch(f"/api/tasks/{task_id}/submit", json={
                "submitHours": RAW_SUBMIT_HOURS,
                "submitDesc": "自动化提交：校验 submitHours 前后空格容错",
                "submitAttachments": "",
            })
            assert response.status_code == 200, response.text
            TaskApi.raise_if_business_failed(response, "DEV 提交任务")
        with allure.step("DB 断言：状态 PENDING_REVIEW，且工时分文不差地落库为 8.5"):
            row = db.fetch_task(task_id)
            assert row["status"] == "PENDING_REVIEW", row
            assert float(row["submit_hours"]) == EXPECTED_SUBMIT_HOURS, row

        with allure.step("PM 调用 PATCH /api/tasks/{id}/audit 传 PASS"):
            response = pm_client.patch(
                f"/api/tasks/{task_id}/audit", json=audit_payload["audit_pass"]
            )
            assert response.status_code == 200, response.text
            TaskApi.raise_if_business_failed(response, "PM 审核任务")
        with allure.step("DB 断言：状态变更为 DONE，最新审核结果为 PASS"):
            row = db.fetch_task(task_id)
            assert row["status"] == "DONE", row
            assert row["latest_audit_result"] == "PASS", row
