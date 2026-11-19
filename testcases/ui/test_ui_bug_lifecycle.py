import allure
import pytest
from selenium.webdriver.common.by import By


@allure.feature("UI 自动化")
@allure.story("缺陷生命周期流转")
class TestBugLifecycleUI:

    @pytest.fixture
    def bug_list_page(self, logged_in_driver, env):
        from pages.bug_list_page import BugListPage
        return BugListPage(logged_in_driver, env["web_base_url"])

    @pytest.fixture
    def bug_detail_page(self, logged_in_driver, env):
        from pages.bug_detail_page import BugDetailPage
        return BugDetailPage(logged_in_driver, env["web_base_url"])

    @allure.title("完整缺陷流转：QA 提 Bug -> DEV 修复 -> QA 关闭")
    def test_bug_full_lifecycle(self, bug_list_page, bug_detail_page, driver, login, project_id):
        import uuid
        title = f"UI缺陷-{uuid.uuid4().hex[:6]}"

        with allure.step("1. 切换为 QA 账号提交缺陷"):
            # 动态注入 QA Token 切换身份
            qa_token = login("qa01")["token"]
            driver.execute_script(f"window.localStorage.setItem('litetrack_token', '{qa_token}')")
            bug_list_page.open(project_id)

            bug_list_page.click(bug_list_page.BTN_CREATE)
            bug_list_page.fill_create_form(
                title=title, project="轻舟自动化验收项目", description="UI自动化提的Bug",
                assignee="开发一号", severity="严重"
            )
            bug_list_page.submit_create()
            # 搜索并等待表格出现该缺陷
            bug_list_page.search(title=title)
            bug_list_page.wait_row(title)

        with allure.step("2. 切换为 DEV 账号进行修复"):
            dev_token = login("dev01")["token"]
            driver.execute_script(f"window.localStorage.setItem('litetrack_token', '{dev_token}')")
            driver.refresh()

            bug_list_page.search(title=title)
            bug_list_page.click_row_action(title, "详情")  # 进入详情页
            bug_detail_page.submit_fix_report(
                root_cause="UI测试：修复了空指针", version="v1.0.1", self_test="自测通过"
            )
            assert bug_detail_page.get_status() == "已修复"

        with allure.step("3. 切换回 QA 账号验证关闭"):
            driver.execute_script(f"window.localStorage.setItem('litetrack_token', '{qa_token}')")
            driver.refresh()

            bug_detail_page.submit_qa_verification(result="验证通过", steps="UI回归通过")
            assert bug_detail_page.get_status() == "已关闭"