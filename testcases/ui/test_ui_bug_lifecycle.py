import allure
import pytest
import uuid
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


@pytest.mark.ui
class TestBugLifecycleUI:

    @pytest.fixture
    def bug_list_page(self, driver, env):
        from pages.bug_list_page import BugListPage
        return BugListPage(driver, env["web_base_url"])

    @pytest.fixture
    def bug_detail_page(self, driver, env):
        from pages.bug_detail_page import BugDetailPage
        return BugDetailPage(driver, env["web_base_url"])

    @pytest.fixture
    def login_page(self, driver, env):
        from pages.login_page import LoginPage
        return LoginPage(driver, env["web_base_url"])

    @pytest.fixture
    def dashboard_page(self, driver, env):
        from pages.dashboard_page import DashboardPage
        return DashboardPage(driver, env["web_base_url"])

    def _wait_bug_status(self, bug_detail_page, expect_status, timeout=15):
        def _match(d):
            try:
                return bug_detail_page.get_status() == expect_status
            except Exception:
                return False

        WebDriverWait(bug_detail_page.driver, timeout).until(_match)

    @allure.title("缺陷完整流转：QA提交缺陷 → DEV工作台点击缺陷修复 → QA工作台验收关闭")
    def test_bug_full_lifecycle_dashboard(
        self,
        bug_list_page,
        bug_detail_page,
        login_page,
        dashboard_page,
        driver,
        env,
        switch_role
    ):
        bug_title = f"BUG-{uuid.uuid4().hex[:8]}"
        assignee_name = "张开发"

        with allure.step("1. QA账号登录，进入缺陷列表页新建并提交缺陷"):
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
                severity="SERIOUS",
                description="复现步骤：打开页面，点击按钮，页面报错",
                expect="正常跳转",
                actual="页面抛出异常"
            )
            bug_list_page.submit_create()
            WebDriverWait(driver, 20).until(
                EC.visibility_of_element_located(bug_list_page.SEARCH_TOOLBAR)
            )

        with allure.step("2. DEV账号登录，打开工作台，在我的缺陷表格点击该缺陷进入详情修复"):
            switch_role("dev01")
            login_page.logout()
            login_page.wait_login_page_display()
            login_page.login(username="dev01", password="123456")
            login_page.wait_until_logged_in()

            dashboard_page.open()
            driver.refresh()
            dashboard_page.click_bug_row(bug_title)

            allure.attach(driver.get_screenshot_as_png(), name="bug_detail_page",
                          attachment_type=allure.attachment_type.PNG)
            allure.attach(driver.page_source, name="bug_detail_html", attachment_type=allure.attachment_type.HTML)

            bug_detail_page.submit_fix_report(
                root_cause="接口参数未做非空校验，触发空指针异常",
                version="V1.1",
                self_test="自测通过，不再报错",
                impact="仅该接口",
                risks="无"
            )
            self._wait_bug_status(bug_detail_page, "已修复")

        with allure.step("3. QA账号登录，打开工作台，找到缺陷并验收关闭"):
            switch_role("qa01")
            login_page.logout()
            login_page.wait_login_page_display()
            login_page.login(username="qa01", password="123456")
            login_page.wait_until_logged_in()

            dashboard_page.open()
            driver.refresh()
            dashboard_page.click_bug_row(bug_title)

            bug_detail_page.submit_qa_verification(
                result="验证通过",
                steps="复现步骤执行通过，功能恢复正常"
            )
            self._wait_bug_status(bug_detail_page, "已关闭")
