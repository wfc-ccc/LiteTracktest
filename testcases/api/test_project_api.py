import allure
import uuid


@allure.feature("API - 项目模块")
class TestProjectApi:

    def test_project_crud(self, admin_client):
        from api.project_api import ProjectApi
        proj_api = ProjectApi(admin_client, base_url="")
        name = f"API测试项目-{uuid.uuid4().hex[:6]}"

        with allure.step("1. 创建项目"):
            res = proj_api._request("POST", "", json={"name": name, "description": "测试", "memberIds": []})
            proj_api.raise_if_business_failed(res, "创建项目") if hasattr(proj_api,
                                                                          'raise_if_business_failed') else None

        with allure.step("2. 查询项目列表，断言存在"):
            res_page = proj_api.get_list(name=name)
            assert res_page["total"] >= 1
            project_id = res_page["records"][0]["id"]

        with allure.step("3. 关闭项目"):
            proj_api.close(project_id)
            assert proj_api.get_detail(project_id)["status"] == "CLOSED"

        with allure.step("4. 重启项目"):
            proj_api.reopen(project_id)
            assert proj_api.get_detail(project_id)["status"] == "ACTIVE"

        with allure.step("5. 删除项目清理数据"):
            proj_api.delete(project_id)