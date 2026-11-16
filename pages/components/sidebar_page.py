"""侧边栏导航组件 POM。

源码是 src/layout/Sidebar.vue。
该组件不依赖特定路由，随主布局常驻，用于验证基于角色的菜单渲染与页面跳转。
"""

from __future__ import annotations

from selenium.webdriver.common.by import By

from pages.base_page import BasePage


class SidebarPage(BasePage):
    # ================= 元素定位器 =================
    LOGO_MARK = (By.CSS_SELECTOR, ".sidebar__logo-mark")

    # 所有的菜单项
    MENU_ITEMS = (By.CSS_SELECTOR, ".sidebar__menu .el-menu-item")
    # 根据菜单名称定位菜单项
    MENU_ITEM_BY_TEXT = (By.XPATH, "//li[contains(@class,'el-menu-item')][.//span[text()='{title}']]")
    # 当前高亮的菜单项
    ACTIVE_MENU = (By.CSS_SELECTOR, ".sidebar__menu .el-menu-item.is-active")

    # ================= 页面动作 =================

    def click_menu(self, title: str) -> None:
        """
        点击侧边栏菜单。
        :param title: 菜单的文本（如：工作台、项目管理、缺陷列表、知识库）
        """
        loc = (self.MENU_ITEM_BY_TEXT[0], self.MENU_ITEM_BY_TEXT[1].replace("{title}", title))
        self.click(loc)

    def get_menu_texts(self) -> list[str]:
        """获取当前用户可见的所有菜单名称列表（用于权限断言）"""
        elements = self.driver.find_elements(*self.MENU_ITEMS)
        return [el.text.strip() for el in elements if el.text.strip()]

    def get_active_menu(self) -> str:
        """获取当前处于高亮激活状态的菜单名称"""
        return self.visible(self.ACTIVE_MENU).text.strip()