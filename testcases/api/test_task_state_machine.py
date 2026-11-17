import allure
from utils.db import DBClient

@allure.feature("API - 任务模块")
class TestTaskStateMachine:

    def test_task_happy_path_with_db(self, pm_client, dev_client, db, project_id, login):
        from api.task_api import TaskApi
        pm_api = TaskApi(pm_client, base_url="")
        dev_api = TaskApi(dev_client, base_url="")
        
        # 1. PM 创建任务并指派给 DEV
        dev_id = login("dev01")["user"]["id"]
        with allure.step("PM 创建任务"):
            pm_api.create({"projectId": project_id, "title": "状态机测试任务", "assigneeId": dev_id})
            # 查到刚创建的任务 ID
            task_id = pm_api.find_id_by_title("状态机测试任务", project_id)
            assert db.fetch_task(task_id)["status"] == "TODO"

        # 2. DEV 接受任务
        with allure.step("DEV 接受任务"):
            dev_api.accept(task_id)
            assert db.fetch_task(task_id)["status"] == "DOING"

        # 3. DEV 提交任务
        with allure.step("DEV 提交任务"):
            dev_api.submit(task_id, {"submitHours": 5, "submitDesc": "开发完成", "submitAttachments": ""})
            assert db.fetch_task(task_id)["status"] == "PENDING_REVIEW"

        # 4. PM 审核打回
        with allure.step("PM 审核不通过"):
            pm_api.audit(task_id, {"auditResult": "REJECT", "auditReason": "代码质量不行"})
            assert db.fetch_task(task_id)["status"] == "DOING"

        # 5. DEV 重新提交，PM 审核通过
        with allure.step("DEV 重新提交并 PM 审核通过"):
            dev_api.submit(task_id, {"submitHours": 2, "submitDesc": "已修复", "submitAttachments": ""})
            pm_api.audit(task_id, {"auditResult": "PASS", "auditReason": "OK"})
            assert db.fetch_task(task_id)["status"] == "DONE"
            
        # 清理数据
        pm_api.delete(task_id)