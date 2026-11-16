"""错误页 POM（403、404 等）。

包含：错误码展示、提示语断言、返回工作台操作。
"""

from __future__ import annotations

from selenium.webdriver.common.by import By

from pages.base_page import BasePage


class ErrorPage(BasePage):
    # ================= 元素定位器 =================
    # 错误码标题 (如 "403" 或 "404")
    ERROR_CODE = (By.CSS_SELECTOR, ".el-result__title h1, .el-result__title p")
    # 副标题/提示语 (如 "抱歉，你没有访问该页面的权限")
    ERROR_SUBTITLE = (By.CSS_SELECTOR, ".el-result__subtitle p")
    # 返回工作台按钮
    BTN_BACK_DASHBOARD = (By.XPATH, "//button[contains(span, '返回工作台')]")

    # ================= 页面动作与断言 =================

    def get_error_code(self) -> str:
        """获取错误码文案（如 403、404）"""
        return self.visible(self.ERROR_CODE).text.strip()

    def get_subtitle(self) -> str:
        """获取错误提示语"""
        return self.visible(self.ERROR_SUBTITLE).text.strip()

    def click_back_dashboard(self) -> None:
        """点击返回工作台按钮"""
        self.click(self.BTN_BACK_DASHBOARD)