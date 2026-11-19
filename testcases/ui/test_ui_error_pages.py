import allure
import pytest

@allure.feature("UI 自动化")
@allure.story("异常路由与错误页")
class TestErrorPagesUI:

    @pytest.fixture
    def error_page(self, driver, env):
        from pages.error_page import ErrorPage
        return ErrorPage(driver, env["web_base_url"])

    @allure.title("验证 404 页面兜底与返回工作台")
    def test_404_page_not_found(self, error_page, driver, login):
        with allure.step("登录后访问一个不存在路由"):
            admin_token = login("admin")["token"]
            driver.get(error_page.base_url)
            driver.execute_script("window.localStorage.setItem('litetrack_token', arguments[0]);", admin_token)
            driver.refresh()
            error_page.open_path("/this-page-does-not-exist-123")

        with allure.step("验证 404 拦截与文案"):
            error_page.visible(error_page.ERROR_CODE)
            assert error_page.get_error_code() == "404"
            assert "抱歉，你访问的页面不存在" in error_page.get_subtitle()

        with allure.step("验证返回工作台"):
            error_page.click_back_dashboard()
            error_page.wait_url("/dashboard")

    @allure.title("验证 403 越权访问拦截")
    def test_403_forbidden_access(self, error_page, driver, login):
        with allure.step("DEV账号，同时写入token和user缓存"):
            dev_data = login("dev01")
            dev_token = dev_data["token"]
            dev_user = dev_data["user"]
            driver.get(error_page.base_url)
            driver.execute_script("""
                localStorage.setItem('litetrack_token', arguments[0]);
                localStorage.setItem('litetrack_user', JSON.stringify(arguments[1]));
            """, dev_token, dev_user)
            driver.refresh()

        with allure.step("dev账号访问仅ADMIN可用的用户管理路由 /users"):
            error_page.open_path("/users")
            print("\n==== 403 DEBUG ====")
            print("current_url: ", driver.current_url)
            allure.attach(
                driver.get_screenshot_as_png(),
                name="403页面快照",
                attachment_type=allure.attachment_type.PNG
            )

        with allure.step("验证 403 拦截"):
            error_page.visible(error_page.ERROR_CODE)
            assert error_page.get_error_code() == "403"
