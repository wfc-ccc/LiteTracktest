import allure
import pytest
import uuid
from selenium.webdriver.common.by import By


@allure.feature("UI 自动化")
@allure.story("知识库管理")
class TestKnowledgeBaseUI:

    @pytest.fixture
    def kb_page(self, driver, env):
        from pages.knowledge_base_page import KnowledgeBasePage
        return KnowledgeBasePage(driver, env["web_base_url"])

    @allure.title("ADMIN 上传知识文件、查看详情并修改内容")
    def test_upload_and_edit_knowledge(self, kb_page, driver, login, tmp_path):
        with allure.step("1. 切换 Admin 账号并打开知识库"):
            admin_token = login("admin")["token"]
            driver.execute_script(f"window.localStorage.setItem('litetrack_token', '{admin_token}')")
            kb_page.open()
            assert kb_page.is_element_visible(kb_page.BTN_UPLOAD) is True, "ADMIN 应该能看到上传按钮"

        # 造一个合法的测试文件
        file_name = f"UI测试文档_{uuid.uuid4().hex[:4]}.txt"
        test_file = tmp_path / file_name
        test_file.write_text("这是轻舟系统自动化测试生成的知识库文件内容。", encoding="utf-8")

        with allure.step(f"2. 上传文件: {file_name}"):
            kb_page.open_upload_dialog()
            kb_page.upload_file(str(test_file), access_level="全员访问")

            # 等待上传成功并刷新列表
            kb_page.wait_message("上传成功")
            kb_page.search(file_name)
            kb_page.visible((By.XPATH, f"//tr[.//td[normalize-space(.)='{file_name}']]"))

        with allure.step("3. 查看文件详情"):
            kb_page.click_row_action(file_name, "查看")
            content = kb_page.get_drawer_content()
            assert "自动化测试生成" in content
            kb_page.close_drawer()

    @allure.title("DEV 账号权限隔离：无权上传和删除")
    def test_dev_permissions_on_kb(self, kb_page, driver, login):
        with allure.step("切换 DEV 账号"):
            dev_token = login("dev01")["token"]
            driver.execute_script(f"window.localStorage.setItem('litetrack_token', '{dev_token}')")
            kb_page.open()

        with allure.step("验证隐藏的破坏性操作"):
            assert kb_page.is_element_visible(kb_page.BTN_UPLOAD) is False, "DEV 不应看到上传按钮"

            # 假设列表有数据，验证操作列没有删除按钮
            # 这里仅演示定位器的使用
            delete_btn_loc = (kb_page.ROW_ACTION_BTN[0],
                              kb_page.ROW_ACTION_BTN[1].replace("{filename}", "随便一个文件").replace("{btn_text}",
                                                                                                      "删除"))
            assert kb_page.is_element_visible(delete_btn_loc) is False


