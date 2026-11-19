import allure
import pytest
import uuid


@allure.feature("UI 自动化")
@allure.story("前端权限隔离校验")
class TestUIPermissionIsolation:

    def test_dev_cannot_see_admin_menus(self, driver, env, login):
        from pages.components.sidebar_page import SidebarPage
        sidebar = SidebarPage(driver, env["web_base_url"])

        with allure.step("切换为 DEV 账号"):
            dev_token = login("dev01")["token"]
            driver.get(env["web_base_url"])
            driver.execute_script(f"window.localStorage.setItem('litetrack_token', '{dev_token}')")
            driver.get(f"{env['web_base_url']}/dashboard")

        with allure.step("验证侧边栏菜单权限"):
            menus = sidebar.get_menu_texts()
            assert "用户管理" not in menus, "DEV 角色不应看到用户管理菜单"
            assert "工作台" in menus, "DEV 角色应该能看到工作台"

    # 修复点1：移除非法的 `login as login_fn` 语法，直接使用 Pytest 注入的 `login` 夹具
    def test_dev_cannot_see_edit_buttons_on_task_board(self, driver, env, login, project_id, pm_task_api):
        from pages.task_board_page import TaskBoardPage
        from selenium.webdriver.common.by import By

        board = TaskBoardPage(driver, env["web_base_url"])

        with allure.step("1. PM 通过 API 造一条任务"):
            assignee_id = login("dev01")["user"]["id"]
            title = f"权限验证-{uuid.uuid4().hex[:6]}"
            pm_task_api.create({"projectId": project_id, "title": title, "assigneeId": assignee_id})

        with allure.step("2. DEV 账号登录并查看看板"):
            dev_token = login("dev01")["token"]
            driver.execute_script(f"window.localStorage.setItem('litetrack_token', '{dev_token}')")

            # 修复点2：注入 Token 后，调用 POM 的 open 方法（内部会 driver.get 刷新页面）
            board.open(project_id)

            # 搜索并等待表格行出现（利用最新 POM 提供的 wait_row）
            board.search(keyword=title)
            board.wait_row(title)

        with allure.step("3. 断言无新建权限"):
            # 验证顶部【新建任务】按钮不存在
            assert board.is_element_visible(board.BTN_CREATE) is False, "DEV 不应有新建任务按钮"

        with allure.step("4. 断言无删除权限"):
            # 修复点3：利用 POM 提供的 TASK_ROW_ACTION 定位器，动态拼接“删除”按钮，验证其不可见
            delete_btn_locator = (
                board.TASK_ROW_ACTION[0],
                board.TASK_ROW_ACTION[1].replace("{title}", title).replace("{btn_text}", "删除")
            )
            assert board.is_element_visible(delete_btn_locator) is False, "DEV 在任务行内不应有删除按钮"