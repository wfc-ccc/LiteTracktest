"""顶部导航栏组件 POM。
源码是 src/layout/Navbar.vue。
包含：侧边栏折叠/展开、用户信息展示（头像、姓名、角色）、退出登录及二次确认。
"""
from __future__ import annotations
from selenium.webdriver.common.by import By
from pages.base_page import BasePage


class NavbarPage(BasePage):
    # ================= 元素定位器 =================
    # 左侧：折叠按钮与标题
    TOGGLE_ICON = (By.CSS_SELECTOR, ".navbar__toggle")
    TITLE = (By.CSS_SELECTOR, ".navbar__title")

    # 右侧：通知中心根节点（NoticeCenter组件挂载在这里，class以NoticeCenter.vue实际根class为准）
    NOTICE_CENTER_ROOT = (By.CSS_SELECTOR, ".notice-center")

    # 右侧：用户下拉区域
    USER_DROPDOWN = (By.CSS_SELECTOR, ".navbar__user")
    USER_AVATAR = (By.CSS_SELECTOR, ".navbar__avatar")
    USER_NAME = (By.CSS_SELECTOR, ".navbar__name")
    USER_ROLE_TAG = (By.CSS_SELECTOR, ".navbar__user .el-tag")

    # 下拉菜单项（Element Plus dropdown会挂载到body，不是嵌套在navbar内部！不要用相对定位）
    DROPDOWN_MENU_LOGOUT = (By.XPATH, "//li[contains(@class,'el-dropdown-menu__item')]//span[text()='退出登录']")

    # 退出确认弹窗（全局 MessageBox，挂载body）
    MSG_BOX = (By.CSS_SELECTOR, ".el-message-box")
    MSG_BOX_TITLE = (By.CSS_SELECTOR, ".el-message-box__title")
    MSG_BOX_CONFIRM = (By.CSS_SELECTOR, ".el-message-box__btns .el-button--primary")
    MSG_BOX_CANCEL = (By.XPATH, "//div[contains(@class,'el-message-box__btns')]//button[.//span[text()='取消']]")

    # ================= 页面动作 =================
    def toggle_sidebar(self) -> None:
        """点击左侧折叠/展开侧边栏"""
        self.click(self.TOGGLE_ICON)

    def get_username(self) -> str:
        """获取当前登录用户的名字"""
        return self.visible(self.USER_NAME).text.strip()

    def get_user_role(self) -> str:
        """获取当前登录用户的角色标签文案（如：管理员、项目经理）"""
        return self.visible(self.USER_ROLE_TAG).text.strip()

    def open_user_dropdown(self) -> None:
        """点击用户区域，展开下拉菜单"""
        self.click(self.USER_DROPDOWN)

    def logout(self, confirm: bool = True) -> None:
        """
        执行退出登录操作。
        :param confirm: True 确认退出；False 取消退出
        """
        self.open_user_dropdown()
        self.click(self.DROPDOWN_MENU_LOGOUT)

        # 等待全局确认弹窗渲染
        self.visible(self.MSG_BOX)

        if confirm:
            self.click(self.MSG_BOX_CONFIRM)
        else:
            self.click(self.MSG_BOX_CANCEL)
