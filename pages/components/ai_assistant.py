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
    LAST_AI_MSG_WRAPPER = (By.XPATH, "(//div[contains(@class,'msg-row--ai')])[last()]//div[contains(@class,'msg-bubble')]")
    LAST_AI_MSG_MARKDOWN = (By.XPATH, "(//div[contains(@class,'msg-row--ai')])[last()]//div[contains(@class,'markdown-body')]")
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

    # ================= 工具：判断元素是否可见（替代 is_element_visible） =================
    def _is_visible(self, locator, timeout=0):
        """自己封装，不依赖基类方法"""
        try:
            self.visible(locator, timeout=timeout)
            return True
        except Exception:
            return False

    # ================= 页面动作 =================
    def open_panel(self) -> None:
        """点击悬浮球打开AI面板，降级等待，无wait_until"""
        self.click(self.FAB_BTN)
        self.visible(self.PANEL, timeout=10)
        self.visible(self.HEADER_TITLE, timeout=10)
        # 轮询等待：欢迎文本 或者 消息行出现，最多10s
        start = time.time()
        while time.time() - start < 10:
            has_welcome = self._is_visible(self.WELCOME_TEXT, timeout=0)
            msg_list = self.driver.find_elements(*self.MSG_ROWS)
            if has_welcome or len(msg_list) > 0:
                break
            time.sleep(0.5)

    def close_panel(self) -> None:
        """关闭面板，用自己封装的 _is_visible"""
        if self._is_visible(self.PANEL, timeout=0):
            self.click(self.BTN_CLOSE)

    def is_panel_maximized(self) -> bool:
        panel = self.visible(self.PANEL)
        width = float(panel.value_of_css_property("width").replace("px", ""))
        window_width = self.driver.execute_script("return window.innerWidth")
        expected_max_width = min(800, window_width - 60)
        return abs(width - expected_max_width) < 10

    # ---------- 对话交互 ----------
    def send_message(self, text: str) -> None:
        textarea = self.visible(self.INPUT_TEXTAREA)
        textarea.clear()
        textarea.send_keys(text)
        textarea.send_keys(Keys.ENTER)

    def upload_file(self, file_path: str) -> None:
        abs_path = os.path.abspath(file_path)
        self.visible(self.BTN_UPLOAD_FILE).send_keys(abs_path)
        self.visible(self.ATTACHMENT_TAG, timeout=10)

    def stop_generating(self) -> None:
        if self._is_visible(self.BTN_STOP, timeout=0):
            self.click(self.BTN_STOP)

    def wait_for_ai_reply(self, timeout: float = 30) -> str:
        start_time = time.time()
        while time.time() - start_time < timeout:
            stop_btn_show = self._is_visible(self.BTN_STOP, timeout=0)
            thinking_show = self._is_visible(self.THINKING_INDICATOR, timeout=0)
            if not stop_btn_show and not thinking_show:
                break
            time.sleep(0.5)

        time.sleep(0.25)
        try:
            el = self.visible(self.LAST_AI_MSG_MARKDOWN, timeout=3)
            return el.text.strip()
        except Exception:
            try:
                el_raw = self.visible(self.LAST_AI_MSG_WRAPPER, timeout=2)
                return el_raw.text.strip()
            except Exception:
                return ""

    def get_last_user_message(self) -> str:
        loc = (By.XPATH, "(//div[contains(@class,'msg-row--user')])[last()]//div[contains(@class,'msg-content')]")
        return self.visible(loc).text.strip()

    def click_new_chat(self) -> None:
        self.click(self.BTN_NEW_CHAT)
        start = time.time()
        while time.time() - start < 10:
            if self._is_visible(self.WELCOME_TEXT, timeout=0):
                break
            time.sleep(0.5)

    # ---------- 历史记录管理 ----------
    def open_history(self) -> None:
        self.click(self.BTN_HISTORY)
        self.visible(self.HISTORY_DRAWER)

    def select_history(self, title: str) -> None:
        loc = (self.HISTORY_ITEM_BY_TITLE[0], self.HISTORY_ITEM_BY_TITLE[1].replace("{title}", title))
        self.click(loc)
        start = time.time()
        while time.time() - start < 10:
            has_welcome = self._is_visible(self.WELCOME_TEXT, timeout=0)
            msg_list = self.driver.find_elements(*self.MSG_ROWS)
            if has_welcome or len(msg_list) > 0:
                break
            time.sleep(0.5)

    def get_history_count(self) -> int:
        return len(self.driver.find_elements(*self.HISTORY_ITEMS))

    # ---------- 文件预览弹窗 ----------
    def preview_file(self) -> str:
        file_card = (By.XPATH, "(//div[contains(@class,'msg-row--user')])[last()]//div[contains(@class,'msg-file')]")
        self.click(file_card)
        self.visible(self.PREVIEW_DIALOG)
        content = self.visible(self.PREVIEW_TEXTAREA).get_attribute("value")
        return content
