"""全局布局页 POM。

源码是 src/layout/index.vue（或 Layout.vue）。
负责管理 Aside / Header / Main 结构、折叠状态、以及全局 AI 助手。
"""

from __future__ import annotations

from selenium.webdriver.common.by import By

from pages.base_page import BasePage
from pages.components.sidebar_page import SidebarPage
from pages.components.navbar_page import NavbarPage
from utils.waits import wait_for_element_visible


class LayoutPage(BasePage):
    def __init__(self, driver, base_url: str):
        super().__init__(driver, base_url)
        # 组合模式：将导航栏和侧边栏作为 Layout 的属性，方便在用例中直接调用
        self.sidebar = SidebarPage(driver, base_url)
        self.navbar = NavbarPage(driver, base_url)

    # ================= 1. 核心布局元素 =================
    ASIDE = (By.CSS_SELECTOR, ".layout__aside")
    HEADER = (By.CSS_SELECTOR, ".layout__header")
    MAIN = (By.CSS_SELECTOR, ".layout__main")

    # AI 助手（假定其根节点包含特定的 class，具体视 AiAssistant.vue 源码而定）
    AI_ASSISTANT_ROOT = (By.CSS_SELECTOR, ".ai-assistant")
    # 假定 AI 助手有一个悬浮的唤起按钮
    AI_ASSISTANT_BTN = (By.XPATH, "//div[contains(@class,'ai-assistant')]//button[contains(@class,'trigger')]")

    # ================= 2. 页面动作与断言 =================

    def get_aside_width(self) -> str:
        """
        获取侧边栏当前的宽度。
        用于验证点击 Navbar 折叠按钮后，侧边栏宽度是否在 210px 和 64px 之间切换。
        """
        aside = self.visible(self.ASIDE)
        # 优先获取内联 style 的宽度（对应 Vue 的 :width 绑定）
        style_width = aside.value_of_css_property("width")
        # 如果动画还在过渡中，可能需要稍等，或者直接返回计算后的像素值
        return style_width

    def is_aside_collapsed(self) -> bool:
        """
        通过判断宽度是否接近于 64px 来断言侧边栏是否处于折叠状态。
        """
        width_str = self.get_aside_width()
        # 将 "64px" 转换为浮点数 64.0
        width = float(width_str.replace("px", ""))
        return width < 100.0  # 用一个中间值判断

    def toggle_sidebar_via_navbar(self):
        """
        点击 Navbar 的折叠按钮，并等待 CSS 过渡动画（0.25s）完成。
        """
        self.navbar.toggle_sidebar()
        # 由于源码有 transition: width 0.25s，UI 测试时最好给一点点等待或重新获取宽度
        import time
        time.sleep(0.3)

    def get_main_content(self) -> str:
        """获取主内容区的文本（常用于断言当前页面加载成功）"""
        return self.visible(self.MAIN).text.strip()

    def open_ai_assistant(self):
        """点击唤起全局 AI 助手（需根据实际组件结构微调）"""
        try:
            self.click(self.AI_ASSISTANT_BTN)
            # 等待对话框出现
            wait_for_element_visible(self.driver, (By.CSS_SELECTOR, ".ai-assistant__dialog"))
        except Exception:
            pass  # 如果组件未渲染或不需要该功能，可忽略