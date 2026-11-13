"""缺陷闭环与七项打回：QA 提报 → DEV 修复 → QA 验证关闭 → QA 打回。

每一步都用 utils/db.py 直连库核对 status，避免只信接口返回。
七项打回重点校验 BugReopenDTO 的必填完整性：少一项必须被拒且不产生副作用，
补齐七项后状态回到 OPEN，且打回分类与详细说明正确落库。
"""

from __future__ import annotations

import uuid

import allure
import pytest

pytestmark = pytest.mark.api

# 七项打回报告的完整字段，与 BugReopenDTO 一致
REOPEN_SEVEN = {
    "reopenReasonType": "原问题仍复现",
    "reopenReasonDesc": "压测到 1500 并发时依然报错",
    "reopenVerifyEnv": "v1.0.1 / 测试环境 / Chrome 120",
    "reopenActualResult": "1500 并发时依然返回 500",
    "reopenExpectedResult": "1500 并发应能正常登录",
    "reopenReproSteps": "JMeter 发起 1500 并发，必现",
    "reopenAttachments": "http://localhost:8081/uploads/error_log.txt",
}
MISSING_FIELD = "reopenAttachments"


def _assert_ok(response, action: str) -> dict:
    """统一响应 Result 的断言：HTTP 200 且业务码 200。"""
    body = response.json()
    assert response.status_code == 200 and body.get("code") == 200, f"{action} 失败: {body}"
    return body


def _find_bug_id(qa_client, title: str, project_id: int) -> int:
    """提交接口返回 Result<Void>，没有 bugId，按唯一标题回查。"""
    response = qa_client.get("/api/bugs", params={
        "projectId": project_id,
        "keyword": title,
        "current": 1,
        "size": 10,
    })
    body = _assert_ok(response, "查询缺陷列表")
    records = (body.get("data") or {}).get("records") or []
    matched = [item for item in records if item.get("title") == title]
    assert len(matched) == 1, f"期望唯一缺陷标题 {title!r}，实际匹配 {len(matched)} 条"
    return int(matched[0]["id"])


@pytest.fixture
def bug_id(qa_client, login, project_id) -> int:
    """QA 提报一条缺陷并指派给 DEV，交出 bug_id。缺陷无删除接口，不做清理。"""
    assignee_id = login("dev01")["user"]["id"]
    title = f"auto-bug-{uuid.uuid4().hex[:12]}"

    response = qa_client.post("/api/bugs", json={
        "projectId": project_id,
        "title": title,
        "description": "1. 打开登录页\n2. 输入正确账号密码\n3. 点击登录，接口返回 500",
        "module": "用户中心",
        "version": "v1.0.0",
        "environment": "Chrome 120, Win10",
        "severity": "HIGH",
        "priority": "HIGH",
        "expectedResult": "登录成功，跳转首页",
        "actualResult": "接口返回 500，页面无响应",
        "assigneeId": assignee_id,
    })
    _assert_ok(response, "QA 提报缺陷")

    return _find_bug_id(qa_client, title, project_id)


def _fix(dev_client, bug_id: int) -> None:
    _assert_ok(dev_client.patch(f"/api/bugs/{bug_id}/fix", json={
        "fixRootCause": "并发过高导致数据库连接池耗尽，已调大连接池并优化 SQL",
        "fixVersionInfo": "v1.0.1 / commit: a1b2c3d",
        "fixSelfTest": "本地压测 1000 并发无报错",
        "fixImpactScope": "影响整个登录模块，建议回归登录用例",
        "fixRisks": "暂无",
        "fixAttachments": "http://localhost:8081/uploads/log1.txt",
    }), "DEV 修复缺陷")


def _close(qa_client, bug_id: int) -> None:
    _assert_ok(qa_client.patch(f"/api/bugs/{bug_id}/close", json={
        "qaTestSteps": "1. 重复登录 10 次\n2. 观察接口是否返回 200",
        "qaTestResult": "验证通过",
        "qaAttachments": "http://localhost:8081/uploads/qa_log.txt",
    }), "QA 验证关闭缺陷")


@allure.feature("缺陷管理")
@allure.story("缺陷闭环")
class TestBugLifecycle:
    @allure.title("QA 提报 → DEV 修复 → QA 验证关闭，每一步 DB 断言状态")
    def test_bug_lifecycle(self, bug_id, db, dev_client, qa_client):
        with allure.step("提报后：DB 状态应为 OPEN"):
            row = db.fetch_bug(bug_id)
            assert row is not None, f"缺陷 {bug_id} 未落库"
            assert row["status"] == "OPEN", row

        with allure.step("DEV 调用 PATCH /api/bugs/{id}/fix 提交修复报告"):
            _fix(dev_client, bug_id)
        with allure.step("DB 断言：状态变更为 FIXED"):
            row = db.fetch_bug(bug_id)
            assert row["status"] == "FIXED", row

        with allure.step("QA 调用 PATCH /api/bugs/{id}/close 验证关闭"):
            _close(qa_client, bug_id)
        with allure.step("DB 断言：状态变更为 CLOSED"):
            row = db.fetch_bug(bug_id)
            assert row["status"] == "CLOSED", row

    @allure.title("七项打回：缺一项被拒且无副作用，补齐七项后回 OPEN 且原因落库")
    def test_reopen_requires_seven_fields(self, bug_id, db, dev_client, qa_client):
        _fix(dev_client, bug_id)
        _close(qa_client, bug_id)
        with allure.step("前置：缺陷已处于 CLOSED，满足打回状态机"):
            assert db.fetch_bug(bug_id)["status"] == "CLOSED"

        with allure.step(f"故意少传 {MISSING_FIELD}，断言业务报错"):
            partial = {key: value for key, value in REOPEN_SEVEN.items() if key != MISSING_FIELD}
            response = qa_client.patch(f"/api/bugs/{bug_id}/reopen", json=partial)
            body = response.json() if response.text else {}
            assert response.status_code >= 400 or body.get("code") != 200, (
                f"缺项请求本应被拒，却返回成功: http={response.status_code}, body={body}"
            )
        with allure.step("DB 断言：打回被拒后状态仍是 CLOSED，未产生副作用"):
            assert db.fetch_bug(bug_id)["status"] == "CLOSED"

        with allure.step("补齐七项后再次打回"):
            _assert_ok(qa_client.patch(f"/api/bugs/{bug_id}/reopen", json=REOPEN_SEVEN), "QA 打回缺陷")
        with allure.step("DB 断言：状态回 OPEN，打回分类与详细说明正确落库"):
            row = db.fetch_bug(bug_id)
            assert row["status"] == "OPEN", row
            assert row["reopen_reason_type"] == REOPEN_SEVEN["reopenReasonType"], row
            assert row["reopen_reason_desc"] == REOPEN_SEVEN["reopenReasonDesc"], row
