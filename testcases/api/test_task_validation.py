import allure
import pytest

@allure.feature("API - 任务模块")
class TestTaskValidation:
    @pytest.mark.parametrize("payload, expect_error", [
        ({"projectId": None, "title": ""}, "标题不能为空"),
        ({"title": "测试任务"}, "项目ID不能为空"),
        ({"projectId": None, "title": "测试", "assigneeId": 999999}, "负责人不存在")
    ])
    def test_create_task_invalid_params(self, pm_client, env, payload, expect_error):
        from api.task_api import TaskApi
        task_api = TaskApi(pm_client, base_url=env["api_base_url"])

        # 动态替换为当前自动化项目ID
        if "projectId" in payload:
            payload["projectId"] = env["project_id"]

        with allure.step(f"测试非法参数: {payload}"):
            body = task_api._request("POST", "", json=payload, skip_code_check=True)
            allure.attach(str(body), name="response", attachment_type=allure.attachment_type.JSON)
            assert body["code"] != 200
            assert expect_error in body["message"]
