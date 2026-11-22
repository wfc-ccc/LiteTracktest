import allure
import uuid
from selenium.webdriver.common.by import By
from utils.waits import wait_for_element_visible, wait_for_element_invisible


@allure.feature("UI 自动化")
@allure.story("前端权限隔离校验")
class TestUIPermissionIsolation:
    @allure.title("验证DEV角色：不可看到管理员菜单，可看到工作台菜单")
    def test_dev_cannot_see_admin_menus(self, driver, env, login):
        """
        权限校验：DEV开发账号侧边栏菜单权限隔离
        预期：
        1. 不展示【用户管理】等管理员菜单
        2. 正常展示【工作台】菜单
        """
        from pages.components.sidebar_page import SidebarPage
        sidebar = SidebarPage(driver, env["web_base_url"])
        # 侧边栏根容器定位器，根据前端实际class修改
        SIDEBAR_ROOT = (By.CSS_SELECTOR, ".sidebar")

        with allure.step("切换为 DEV 账号：先访问前端域名，再注入token"):
            dev_token = login("dev01")["token"]
            # 先打开前端页面，保证域名合法，才能操作localStorage
            driver.get(env["web_base_url"])
            # 注入登录凭证token
            driver.execute_script(f"window.localStorage.setItem('litetrack_token', '{dev_token}')")
            # 跳转到工作台页面
            driver.get(f"{env['web_base_url']}/dashboard")
            # 等待侧边栏容器渲染完成
            wait_for_element_visible(driver, SIDEBAR_ROOT, timeout=10)

        with allure.step("获取侧边栏菜单文本，校验菜单权限"):
            menus = sidebar.get_menu_texts()
            # 管理员菜单对DEV不可见
            assert "用户管理" not in menus, "DEV 角色不应看到用户管理菜单"
            # 基础工作台菜单DEV可见
            assert "工作台" in menus, "DEV 角色应该能看到工作台"

    @allure.title("验证DEV角色：任务看板无新建、删除按钮权限")
    def test_dev_cannot_see_edit_buttons_on_task_board(self, driver, env, login, project_id, pm_task_api):
        """
        权限校验：DEV开发账号在任务看板的操作按钮权限隔离
        前置：PM账号API创建一条任务，分配给DEV
        预期：
        1. 顶部【新建任务】按钮不存在
        2. 任务行内【删除】按钮不存在
        """
        from pages.task_board_page import TaskBoardPage
        board = TaskBoardPage(driver, env["web_base_url"])

        with allure.step("1. PM 通过API创建测试任务，分配给DEV账号"):
            assignee_id = login("dev01")["user"]["id"]
            title = f"权限验证-{uuid.uuid4().hex[:6]}"
            pm_task_api.create({"projectId": project_id, "title": title, "assigneeId": assignee_id})

        with allure.step("2. DEV账号注入token，打开任务看板页面"):
            dev_token = login("dev01")["token"]
            # 先访问前端地址，解决data空白页禁止localStorage报错
            driver.get(env["web_base_url"])
            driver.execute_script(f"window.localStorage.setItem('litetrack_token', '{dev_token}')")
            # 打开对应项目的看板页面
            board.open(project_id)
            # 搜索刚才创建的任务
            board.search(keyword=title)
            # 等待任务行渲染出现
            board.wait_row(title)

        with allure.step("3. 校验：DEV没有新建任务按钮"):
            wait_for_element_invisible(driver, board.BTN_CREATE, timeout=5)

        with allure.step("4. 校验：DEV在任务行内没有删除按钮"):
            delete_btn_locator = (
                board.TASK_ROW_ACTION[0],
                board.TASK_ROW_ACTION[1].replace("{title}", title).replace("{btn_text}", "删除")
            )
            wait_for_element_invisible(driver, delete_btn_locator, timeout=5)
