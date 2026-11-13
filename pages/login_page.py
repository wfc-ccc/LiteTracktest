"""登录页 POM。

源码是 src/views/Login.vue（不是 views/login/index.vue）。
页面没有 data-test，定位器用登录卡片上稳定的 class 与 placeholder。
"""

from __future__ import annotations

from selenium.webdriver.common.by import By

from pages.base_page import BasePage
from utils.waits import wait_for_url_contains


class LoginPage(BasePage):
    TITLE = (By.CSS_SELECTOR, ".login__title")
    USERNAME = (By.CSS_SELECTOR, ".login__card input[placeholder='请输入用户名']")
    PASSWORD = (By.CSS_SELECTOR, ".login__card input[placeholder='请输入密码']")
    SUBMIT = (By.CSS_SELECTOR, "button.login__submit")
    # 登录成功后布局顶栏，见 layout/Navbar.vue
    NAVBAR_TITLE = (By.CSS_SELECTOR, ".navbar__title")
    NAVBAR_NAME = (By.CSS_SELECTOR, ".navbar__name")

    def open(self) -> None:
        self.open_path("/login")
        self.visible(self.TITLE)

    def login(self, username: str, password: str) -> None:
        self.type_text(self.USERNAME, username)
        self.type_text(self.PASSWORD, password)
        self.click(self.SUBMIT)

    def wait_until_logged_in(self) -> str:
        """等待进入工作台，返回顶栏显示的姓名。"""
        wait_for_url_contains(self.driver, "/dashboard")
        self.visible(self.NAVBAR_TITLE)
        return self.visible(self.NAVBAR_NAME).text.strip()

    def logout(self) -> None:
        """清掉本地令牌后回到登录页，用于用例中途切换身份。

        路由守卫只认 localStorage['litetrack_token']，不清掉时访问 /login 会被弹回工作台。
        """
        self.driver.execute_script("window.localStorage.clear()")
        self.open()
