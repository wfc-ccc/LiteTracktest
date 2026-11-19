import allure
import pytest
import uuid
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


@pytest.mark.ui
class TestGlobalComponentsUI:

    @pytest.fixture
    def notice_center(self, driver, env):
        from pages.components.notice_center import NoticeCenterComponent
        return NoticeCenterComponent(driver, env["web_base_url"])

    @pytest.fixture
    def login_page(self, driver, env):
        from pages.login_page import LoginPage
        return LoginPage(driver, env["web_base_url"])

    @pytest.fixture
    def dashboard_page(self, driver, env):
        from pages.dashboard_page import DashboardPage
        return DashboardPage(driver, env["web_base_url"])

    @pytest.fixture
    def bug_list_page(self, driver, env):
        from pages.bug_list_page import BugListPage
        return BugListPage(driver, env["web_base_url"])

    def _wait_notice_item_exists(self, notice_center, notice_title, timeout=15):
        def _match(d):
            return notice_center.is_notice_exist(notice_title)
        WebDriverWait(notice_center.driver, timeout).until(_match, message=f"等待通知【{notice_title}】超时未出现")

    @allure.title("通知中心：QA提交缺陷 → DEV收到通知，打开通知面板、一键已读")
    def test_notice_center_operations(
        self,
        notice_center,
        login_page,
        dashboard_page,
        bug_list_page,
        driver,
        env,
        switch_role
    ):
        bug_title = f"BUG-NOTICE-{uuid.uuid4().hex[:8]}"
        assignee_name = env.get("dev_user_realname", "张开发")  # 从环境变量读，避免硬编码

        with allure.step("1. QA账号登录，新建缺陷指派给开发，产生通知消息"):
            switch_role("qa01")
            login_page.logout()
            login_page.wait_login_page_display()
            login_page.login(username="qa01", password="123456")
            login_page.wait_until_logged_in()

            bug_list_page.open(env["project_id"])
            bug_list_page.open_create_dialog()
            bug_list_page.fill_create_form(
                title=bug_title,
                assignee=assignee_name,
                module="登录模块",
                found_version="V1.0",
                env="测试环境",
                priority="MEDIUM",
                severity="严重",
                description="复现步骤：打开页面，点击按钮，页面报错",
                expect="正常跳转",
                actual="页面抛出异常"
            )
            bug_list_page.submit_create()
            # 等待列表加载，同时可增加缺陷出现在列表的校验（可选）
            WebDriverWait(driver, 20).until(
                EC.visibility_of_element_located(bug_list_page.SEARCH_TOOLBAR)
            )

        with allure.step("2. DEV账号登录，进入工作台，打开通知铃铛面板"):
            switch_role("dev01")
            login_page.logout()
            login_page.wait_login_page_display()
            login_page.login(username="dev01", password="123456")
            login_page.wait_until_logged_in()

            dashboard_page.open()
            # 等待导航头部（和你layout源码class对齐：layout__header）
            notice_center.visible((By.CSS_SELECTOR, ".layout__header"), timeout=15)
            allure.attach(
                driver.get_screenshot_as_png(),
                name="打开通知面板前",
                attachment_type=allure.attachment_type.PNG
            )
            notice_center.open_panel(timeout=20)
            allure.attach(
                driver.get_screenshot_as_png(),
                name="通知面板展开",
                attachment_type=allure.attachment_type.PNG
            )

        with allure.step("3. 校验通知列表存在缺陷通知，执行一键已读"):
            self._wait_notice_item_exists(notice_center, bug_title)
            # 记录一键已读前未读数
            before_read = notice_center.get_unread_count()
            notice_center.click_mark_all_read()
            # 加断言：一键已读后，未读角标消失/未读数为0
            after_read = notice_center.get_unread_count()
            assert before_read >= 1, "一键已读前未读数量不能为0"
            assert after_read == 0, f"一键已读失败，未读数量仍然是 {after_read}"

        with allure.step("4. 后置：关闭通知面板（可选）"):
            # 点击页面空白处关闭面板，避免污染后续用例
            driver.find_element(By.CSS_SELECTOR, ".layout__main").click()
            WebDriverWait(driver, 3).until(
                EC.invisibility_of_element_located(notice_center.PANEL)
            )
