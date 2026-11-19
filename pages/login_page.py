"""登录页 POM。 源码是 src/views/Login.vue。 页面没有 data-test，定位器用登录卡片上稳定的 class、placeholder 以及 Element Plus 的默认类名。 """
from __future__ import annotations

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from pages.base_page import BasePage
from utils.waits import wait_for_url_contains


class LoginPage(BasePage):
    # ================= 元素定位器 =================
    TITLE = (By.CSS_SELECTOR, ".login__title")
    USERNAME = (By.CSS_SELECTOR, ".login__card input[placeholder='请输入用户名']")
    PASSWORD = (By.CSS_SELECTOR, ".login__card input[placeholder='请输入密码']")
    SUBMIT = (By.CSS_SELECTOR, "button.login__submit")

    # 表单校验错误提示 (Element Plus 默认类名)
    FORM_ERROR = (By.CSS_SELECTOR, ".el-form-item__error")

    # 全局轻提示 (挂在 body 上，不在表单内)
    MESSAGE_TOAST = (By.CSS_SELECTOR, ".el-message__content")

    # 登录成功后布局顶栏，见 layout/Navbar.vue
    NAVBAR_TITLE = (By.CSS_SELECTOR, ".navbar__title")
    NAVBAR_NAME = (By.CSS_SELECTOR, ".navbar__name")

    # ================= 页面动作 =================
    def open(self) -> None:
        """打开登录页：先清空本地token，避免路由守卫自动跳转dashboard"""
        # 🌟 核心修复：如果当前还是 data:, 空白页，必须先访问一次真实域名建立 origin
        if not self.driver.current_url.startswith(self.base_url):
            self.driver.get(self.base_url)

        # 此时可以安全地清除存储和 Cookie 了
        self.driver.execute_script("window.localStorage.clear();")
        self.driver.execute_script("window.sessionStorage.clear();")
        self.driver.delete_all_cookies()

        self.open_path("/login")
        # 等待路由稳定，确认没有被重定向到dashboard
        WebDriverWait(self.driver, 10).until(
            lambda d: "/dashboard" not in d.current_url
        )
        # 等待登录标题元素
        self.visible(self.TITLE)

    def wait_login_page_display(self, timeout=10):
        """等待登录页面卡片加载完成，登出切换身份时使用"""
        self.visible(self.USERNAME, timeout=timeout)

    def login(self, username: str, password: str) -> None:
        """执行登录动作（点击按钮）"""
        self.type_text(self.USERNAME, username)
        self.type_text(self.PASSWORD, password)
        self.click(self.SUBMIT)

    def login_by_enter(self, username: str, password: str) -> None:
        """执行登录动作（使用密码框回车提交），对应源码的 @keyup.enter"""
        self.type_text(self.USERNAME, username)
        self.type_text(self.PASSWORD, password)
        # 按回车键
        self.visible(self.PASSWORD).send_keys("\n")

    def wait_until_logged_in(self) -> str:
        """等待进入工作台，返回顶栏显示的姓名。"""
        wait_for_url_contains(self.driver, "/dashboard")
        self.visible(self.NAVBAR_TITLE)
        return self.visible(self.NAVBAR_NAME).text.strip()

    def logout(self) -> None:
        """清掉本地令牌后回到登录页，用于用例中途切换身份。
        路由守卫只认 localStorage['litetrack_token']，不清掉时访问 /login 会被弹回工作台。
        """
        # 🌟 核心修复：确保在真实页面上清空 Token
        if not self.driver.current_url.startswith(self.base_url):
            self.driver.get(self.base_url)

        self.driver.execute_script("window.localStorage.clear()")
        self.open()

    # ================= 断言辅助 =================
    def get_form_error_text(self) -> str:
        """获取表单的校验错误信息（用于测试必填、密码长度等前端校验）"""
        return self.visible(self.FORM_ERROR).text.strip()

    def get_message_text(self) -> str:
        """获取全局提示信息（如 '欢迎回来' 或者 '用户名或密码错误'）"""
        return self.visible(self.MESSAGE_TOAST).text.strip()
