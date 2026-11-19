import allure
import pytest
import uuid


@allure.feature("UI 自动化")
@allure.story("后台配置管理")
class TestManageOperationsUI:

    def test_create_user_flow(self, driver, env, login):
        from pages.user_manage_page import UserManagePage
        user_page = UserManagePage(driver, env["web_base_url"])

        with allure.step("ADMIN 登录并进入用户管理"):
            admin_token = login("admin")["token"]
            driver.execute_script(f"window.localStorage.setItem('litetrack_token', '{admin_token}')")
            user_page.open()

        username = f"ui_user_{uuid.uuid4().hex[:4]}"
        with allure.step(f"创建新用户: {username}"):
            user_page.open_create_dialog()
            user_page.fill_form(
                username=username, password="123456",
                real_name="UI测试账号", role_text="测试"
            )
            user_page.submit_dialog()

        with allure.step("搜索并验证用户状态"):
            user_page.search(username=username)
            assert user_page.get_row_status(username) == "启用"

        with allure.step("删除该用户（清理数据）"):
            user_page.click_row_action(username, "删除")
            user_page.confirm_message_box()

    def test_project_member_readonly_check(self, driver, env, login, project_id):
        from pages.project_manage_page import ProjectManagePage
        proj_page = ProjectManagePage(driver, env["web_base_url"])

        with allure.step("PM 登录并进入项目列表"):
            pm_token = login("pm01")["token"]
            driver.execute_script(f"window.localStorage.setItem('litetrack_token', '{pm_token}')")
            proj_page.open()

        with allure.step("查看系统内置项目成员"):
            # 假设 env 里配置的项目处于 ACTIVE 状态，可以正常管理成员
            proj_page.search(name="轻舟自动化验收项目")
            proj_page.click_row_action("轻舟自动化验收项目", "成员")

            # 验证弹窗渲染和关闭
            assert proj_page.is_member_readonly() is False