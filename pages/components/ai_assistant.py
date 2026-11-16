"""全局 AI 助手组件 POM。

源码是 src/components/AiAssistant.vue。
涉及：悬浮球、主面板展开/收起、文件上传解析、流式对话发送与等待、历史记录管理。
"""

from __future__ import annotations
import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement

from pages.base_page import BasePage
from utils.waits import wait_for_element_visible


class AiAssistantComponent(BasePage):
    # ================= 1. 悬浮球与面板基础 =================
    FAB_BTN = (By.CSS_SELECTOR, ".ai-fab")
    PANEL = (By.CSS_SELECTOR, ".ai-panel")
    HEADER_TITLE = (By.CSS_SELECTOR, ".ai-header__title")

    # 头部按钮
    BTN_HISTORY = (By.CSS_SELECTOR, ".history-btn")
    BTN_NEW_CHAT = (By.CSS_SELECTOR, ".ai-header__right .icon-btn[title='新对话']")
    BTN_MAXIMIZE = (By.CSS_SELECTOR,
                    ".ai-header__right .icon-btn[title='最大化'], .ai-header__right .icon-btn[title='还原']")
    BTN_CLOSE = (By.CSS_SELECTOR, ".ai-header__right .icon-btn--close")

    # ================= 2. 消息区 =================
    WELCOME_TEXT = (By.CSS_SELECTOR, ".ai-welcome h3")
    MSG_ROWS = (By.CSS_SELECTOR, ".msg-row")
    # 最后一条 AI 的回复内容容器
    LAST_AI_MSG = (By.XPATH, "(//div[contains(@class,'msg-row--ai')])[last()]//div[contains(@class,'markdown-body')]")
    THINKING_INDICATOR = (By.CSS_SELECTOR, ".msg-bubble.thinking")

    # ================= 3. 输入区 =================
    INPUT_TEXTAREA = (By.CSS_SELECTOR, ".footer-input textarea")
    BTN_UPLOAD_FILE = (By.CSS_SELECTOR, ".footer-actions input[type='file']")
    ATTACHMENT_TAG = (By.CSS_SELECTOR, ".attachment-tag .el-tag")
    BTN_SEND = (By.CSS_SELECTOR, ".send-btn")
    BTN_STOP = (By.CSS_SELECTOR, ".stop-btn")

    # ================= 4. 历史记录侧边栏 =================
    HISTORY_DRAWER = (By.CSS_SELECTOR, ".ai-history-drawer-el")
    HISTORY_ITEMS = (By.CSS_SELECTOR, ".history-item")
    HISTORY_ITEM_BY_TITLE = (By.XPATH,
                             "//div[contains(@class,'history-item')][.//span[contains(@class,'history-item__title') and text()='{title}']]")

    # ================= 5. 文件预览弹窗 =================
    PREVIEW_DIALOG = (By.CSS_SELECTOR, ".file-preview-dialog")
    PREVIEW_TEXTAREA = (By.CSS_SELECTOR, ".file-preview-dialog textarea")

    # ================= 页面动作 =================

    def open_panel(self) -> None:
        """点击悬浮球打开 AI 面板"""
        self.click(self.FAB_BTN)
        self.visible(self.PANEL)
        self.visible(self.HEADER_TITLE)

    def close_panel(self) -> None:
        """点击面板上的关闭按钮"""
        if self.is_element_visible(self.PANEL):
            self.click(self.BTN_CLOSE)

    def is_panel_maximized(self) -> bool:
        """通过判断面板宽度是否接近屏幕宽度来验证是否最大化"""
        panel = self.visible(self.PANEL)
        width = float(panel.value_of_css_property("width").replace("px", ""))
        # 源码 getMaxSize 中设定最大宽度为 min(800, window.innerWidth - 60)
        window_width = self.driver.execute_script("return window.innerWidth")
        expected_max_width = min(800, window_width - 60)
        return abs(width - expected_max_width) < 10

    # ---------- 对话交互 ----------

    def send_message(self, text: str) -> None:
        """在输入框输入文本并发送（模拟回车）"""
        textarea = self.visible(self.INPUT_TEXTAREA)
        textarea.clear()
        textarea.send_keys(text)
        # 源码中通过 @keydown 监听了 Enter 键
        textarea.send_keys(Keys.ENTER)

    def upload_file(self, file_path: str) -> None:
        """上传附件"""
        abs_path = os.path.abspath(file_path)
        # 直接向隐藏的 input type=file 发送路径
        self.visible(self.BTN_UPLOAD_FILE).send_keys(abs_path)
        # 等待附件 Tag 出现，证明解析完成
        self.visible(self.ATTACHMENT_TAG)

    def stop_generating(self) -> None:
        """点击停止生成"""
        if self.is_element_visible(self.BTN_STOP):
            self.click(self.BTN_STOP)

    def wait_for_ai_reply(self, timeout: float = 30) -> str:
        """
        等待 AI 流式输出完成，并返回最后一条回复的文本。
        由于是流式输出，核心策略是：等待“停止”按钮消失，且“发送”按钮重新出现。
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            # 如果还有停止按钮，说明还在生成中
            if self.is_element_visible(self.BTN_STOP):
                time.sleep(0.5)
                continue
            # 如果停止按钮消失，说明生成结束
            break

        # 🚀 微调：增加一点点的缓冲时间，确保最后一段流式文本已被 Vue 渲染到 DOM
        time.sleep(0.2)

        try:
            # 如果此时还有“思考中”的动画，等待它消失
            if self.is_element_visible(self.THINKING_INDICATOR):
                time.sleep(0.5)

            # 获取最后一条 AI 消息的文本
            last_msg = self.visible(self.LAST_AI_MSG, timeout=5)
            return last_msg.text.strip()
        except Exception:
            return ""

    def get_last_user_message(self) -> str:
        """获取最后一条用户发送的消息文本"""
        loc = (By.XPATH, "(//div[contains(@class,'msg-row--user')])[last()]//div[contains(@class,'msg-content')]")
        return self.visible(loc).text.strip()

    # ---------- 历史记录管理 ----------

    def open_history(self) -> None:
        """打开历史记录抽屉"""
        self.click(self.BTN_HISTORY)
        self.visible(self.HISTORY_DRAWER)

    def select_history(self, title: str) -> None:
        """选择某个历史会话"""
        loc = (self.HISTORY_ITEM_BY_TITLE[0], self.HISTORY_ITEM_BY_TITLE[1].replace("{title}", title))
        self.click(loc)
        # 选完后侧边栏会自动关闭

    def get_history_count(self) -> int:
        """获取历史记录数量"""
        return len(self.driver.find_elements(*self.HISTORY_ITEMS))

    # ---------- 预览弹窗 ----------

    def preview_file(self) -> str:
        """点击消息里的文件卡片，并获取弹窗里的文件内容"""
        # 点击最后一条用户消息里的文件卡片
        file_card = (By.XPATH, "(//div[contains(@class,'msg-row--user')])[last()]//div[contains(@class,'msg-file')]")
        self.click(file_card)

        # 等待弹窗出现并获取内容
        self.visible(self.PREVIEW_DIALOG)
        content = self.visible(self.PREVIEW_TEXTAREA).get_attribute("value")
        return content