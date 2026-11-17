import allure
import uuid

@allure.feature("API - 项目模块")
class TestProjectApi:
    def test_project_crud(self, admin_client, env, login):
        from api.project_api import ProjectApi
        # 修复：从环境拿base_url，不再传空
        proj_api = ProjectApi(admin_client, base_url=env["api_base_url"])
        # 动态获取admin作为负责人
        admin_info = login("admin")
        owner_id = admin_info["user"]["id"]

        name = f"API测试项目-{uuid.uuid4().hex[:6]}"
        project_id = None

        try:
            with allure.step("1. 创建项目"):
                # 补上ownerId，满足后端校验
                res = proj_api._request(
                    "POST",
                    "",
                    json={
                        "name": name,
                        "description": "测试",
                        "memberIds": [],
                        "ownerId": owner_id
                    }
                )
                if hasattr(proj_api, 'raise_if_business_failed'):
                    proj_api.raise_if_business_failed(res, "创建项目")

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

        finally:
            # 兜底：不管中间哪一步失败，只要拿到id就尝试删除
            if project_id:
                with allure.step("后置清理：删除测试项目"):
                    try:
                        proj_api.delete(project_id)
                        print(f"[clean] 测试项目 {project_id} 已删除")
                    except Exception as e:
                        print(f"[warn] 删除项目 {project_id} 失败：{e}")
