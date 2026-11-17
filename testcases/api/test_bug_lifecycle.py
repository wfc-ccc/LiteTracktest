import allure
from utils.db import DBClient

@allure.feature("API - 缺陷模块")
class TestBugLifecycle:

    def test_bug_full_flow(self, qa_client, dev_client, db, project_id, login):
        from api.bug_api import BugApi
        qa_api = BugApi(qa_client, base_url="")
        dev_api = BugApi(dev_client, base_url="")
        
        dev_id = login("dev01")["user"]["id"]
        title = "API缺陷流转测试"
        
        # 1. QA 提交缺陷
        with allure.step("QA 提交缺陷"):
            qa_api.create({
                "projectId": project_id, "title": title, "severity": "HIGH",
                "priority": "HIGH", "description": "测试步骤", "assigneeId": dev_id
            })
            # 查库拿 ID
            row = db.query_one("SELECT id FROM bug WHERE title=%s ORDER BY id DESC LIMIT 1", (title,))
            bug_id = row["id"]
            assert db.fetch_bug(bug_id)["status"] == "OPEN"

        # 2. DEV 提交修复报告
        with allure.step("DEV 修复缺陷"):
            dev_api.fix(bug_id, {"fixRootCause": "修复说明", "fixVersionInfo": "v1.0"})
            assert db.fetch_bug(bug_id)["status"] == "FIXED"

        # 3. QA 验证关闭
        with allure.step("QA 验证关闭"):
            qa_api.close(bug_id, {"qaTestResult": "PASS", "qaTestSteps": "回归通过"})
            assert db.fetch_bug(bug_id)["status"] == "CLOSED"