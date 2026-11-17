import allure
import pytest

@allure.feature("API - 任务模块")
class TestTaskValidation:

    @pytest.mark.parametrize("payload, expect_error", [
        ({"projectId": 1, "title": ""}, "标题不能为空"),
        ({"title": "测试任务"}, "项目ID不能为空"),
        ({"projectId": 1, "title": "测试", "assigneeId": 999999}, "负责人不存在")
    ])
    def test_create_task_invalid_params(self, pm_client, payload, expect_error):
        from api.task_api import TaskApi
        task_api = TaskApi(pm_client, base_url="")
        
        with allure.step(f"测试非法参数: {payload}"):
            res = task_api.create(payload)
            body = res.json()
            assert body["code"] != 200
            assert expect_error in body["message"] or "参数" in body["message"]