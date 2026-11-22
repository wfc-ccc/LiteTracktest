"""登录页 POM。

源码是 src/views/Login.vue。
页面没有 data-test，定位器用登录卡片上稳定的 class、placeholder 以及 Element Plus 的默认类名。

【本版新增】账号查找、登录后跳转校验、失败诊断全部收进本页面对象，
用例只调 `login_page.login_as(env, "pm01")`，不用自己拼 assert / 抓 toast。
"""
from __future__ import annotations

from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait

from pages.base_page import BasePage
from utils.waits import wait_for_url_contains


class LoginFailed(AssertionError):
    """登录没能进入 /dashboard。

    特意继承 AssertionError：pytest 会把它按「断言失败」展示（不是 error），
    同时又是个具名异常，用例层可以直接 except 它做额外处理。
    """


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

    def wait_login_page_display(self, timeout: int = 10) -> None:
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

    # ================= 账号与登录编排（用例直接调用） =================
    @staticmethod
    def account(env: dict, account_key: str) -> tuple:
        """从 env.yaml 的 accounts 里取 (username, password)。

        缺账号或密码时直接抛 LoginFailed，别拿着空串去点登录再报「没进 /dashboard」。
        """
        accounts = env.get("accounts") or {}
        acc = accounts.get(account_key)
        if not acc:
            raise LoginFailed(
                f"env.yaml 的 accounts 里没有账号 {account_key!r}，现有：{sorted(accounts)}"
            )
        username = str(acc.get("username") or account_key)
        password = str(acc.get("password") or "")
        if not password:
            raise LoginFailed(f"env.yaml 的 accounts.{account_key} 没有配置 password")
        return username, password

    def get_error_detail(self) -> str:
        """把页面上的 toast / 表单校验错误抓成一行，用于登录失败诊断。"""
        parts = []
        for sel in (".el-message__content", ".el-form-item__error"):
            for e in self.driver.find_elements(By.CSS_SELECTOR, sel):
                try:
                    if e.is_displayed():
                        t = (e.text or "").strip()
                        if t:
                            parts.append(f"{sel}={t!r}")
                except Exception:
                    continue
        return "; ".join(parts) or "（页面上没有 toast / 表单错误）"

    def login_as(self, env: dict, account_key: str) -> str:
        """按 env.yaml 的账号键登录，并确认真的进了 /dashboard，返回顶栏姓名。

        失败抛 LoginFailed（AssertionError 子类），消息里带当前 URL 和页面提示，
        能区分「密码错」「账号被禁」「前端没跳转」。
        """
        username, password = self.account(env, account_key)
        print(f"[LOGIN] {account_key} 登录 → {username}")
        self.open()
        self.login(username, password)
        try:
            name = self.wait_until_logged_in()
        except Exception as e:
            raise LoginFailed(
                f"{account_key} 登录后没有进入 /dashboard，当前 URL={self.driver.current_url}；"
                f"提示：{self.get_error_detail()}"
            ) from e
        print(f"[LOGIN] {account_key} 登录成功，顶栏姓名 = {name!r}")
        return name

    # ================= 断言辅助 =================
    def get_form_error_text(self) -> str:
        """获取表单的校验错误信息（用于测试必填、密码长度等前端校验）"""
        return self.visible(self.FORM_ERROR).text.strip()

    def get_message_text(self) -> str:
        """获取全局提示信息（如 '欢迎回来' 或者 '用户名或密码错误'）"""
        return self.visible(self.MESSAGE_TOAST).text.strip()
