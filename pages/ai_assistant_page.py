"""AI 助手对话面板 POM。

源码是 frontend/components/AiAssistant.vue（**全局悬浮组件**，不是独立路由页）。

========== 源码事实（必须对齐） ==========
1. 入口是悬浮球 `.ai-fab`（fixed 右下角），点它 toggle 面板 `.ai-panel`。
   面板是 fixed 定位、默认 450×700，右侧 30px、底部 100px；关闭用头部 `.icon-btn--close`。
2. 头部：`.ai-header__title` = 「轻舟 AI 助手」；
   `.history-btn`（历史记录）、`.icon-btn[title='新对话']`、
   `.icon-btn[title='最大化']` / `[title='还原']`、`.icon-btn--close`。
3. 消息区 `.ai-messages`：
   空态 `.ai-welcome`（「你好，我是轻舟 AI」）；
   用户气泡 `.msg-row--user > .msg-bubble`（纯文本 `.msg-content` 或文件卡 `.msg-file`）；
   AI 气泡 `.msg-row--ai > .msg-bubble`：生成中 `div[style*=pre-wrap]` + 头部 `.thinking`（「正在思考...」），
   isEnd 之后换成 `.markdown-body`（v-html 渲染 marked 结果）。
   末尾固定 `.ai-disclaimer`（「内容由 AI 生成，仅供参考」）。
4. 输入区：`.footer-input textarea`（placeholder「学习或工作有困惑？问问轻舟 AI 吧～」）；
   `.send-btn`（v-if !isGenerating，:disabled="!input.trim()"）；
   `.stop-btn`（v-else，文案「停止」）；附件图标 `.action-icon` 包在 el-upload 里，
   文件 input 是 `.ai-panel input[type='file']`，accept=".txt,.pdf,.md"；
   已选附件 `.attachment-tag .el-tag`（可关闭）。
5. 历史抽屉：`el-drawer` class `ai-history-drawer-el`，`:append-to-body="false"`（**渲染在面板内部**）；
   条目 `.history-item`，标题 `.history-item__title`，当前会话 `.history-item--active`，
   更多按钮 `.history-item__more`（**默认 opacity:0，必须 hover 才出现**），
   下拉项 `.el-dropdown-menu__item`：重命名 / 置顶（或取消置顶）/ 删除；
   空态 `el-empty` description「暂无历史」。
6. 重命名走 `ElMessageBox.prompt`（标题「重命名」，input 为 `.el-message-box__input input`，确认按钮「确定」）；
   删除走 `ElMessageBox.confirm`（标题「提示」，确认按钮文案「删除」）。
7. 附件原文预览 `el-dialog` class `file-preview-dialog`（append-to-body），
   只读 textarea 里是文件正文，footer 按钮「关闭」。
8. Toast：新对话 → 「已开启新对话」；重命名 → 「已重命名」。

========== 等待规范 ==========
全文件不使用 time.sleep；等待统一交给 WebDriverWait（_wait / _wait_bool / wait_visible）。
流式回复用「.thinking 消失 + .markdown-body 出现且有文本 + .send-btn 复现」三条件收敛，
避免只等固定秒数造成的假通过/假失败。
"""
from __future__ import annotations

import os
import time

from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from pages.base_page import BasePage

WAIT_IGNORED = (NoSuchElementException, StaleElementReferenceException)


class AiAssistantPage(BasePage):

    # ---------- 面板本体 ----------
    FAB = (By.CSS_SELECTOR, ".ai-fab")
    PANEL = (By.CSS_SELECTOR, ".ai-panel")
    HEADER_TITLE = (By.CSS_SELECTOR, ".ai-header__title")
    BTN_HISTORY = (By.CSS_SELECTOR, ".ai-panel .history-btn")
    BTN_NEW = (By.CSS_SELECTOR, ".ai-panel .icon-btn[title='新对话']")
    BTN_MAXIMIZE = (
        By.XPATH,
        "//div[contains(@class,'ai-panel')]//button[@title='最大化' or @title='还原']",
    )
    BTN_CLOSE = (By.CSS_SELECTOR, ".ai-panel .icon-btn--close")

    # ---------- 消息区 ----------
    MESSAGES = (By.CSS_SELECTOR, ".ai-panel .ai-messages")
    WELCOME = (By.CSS_SELECTOR, ".ai-panel .ai-welcome")
    ROW_USER = (By.CSS_SELECTOR, ".ai-panel .msg-row--user")
    ROW_AI = (By.CSS_SELECTOR, ".ai-panel .msg-row--ai")
    BUBBLE = (By.CSS_SELECTOR, ".ai-panel .msg-bubble")
    THINKING = (By.CSS_SELECTOR, ".ai-panel .msg-bubble.thinking")
    MARKDOWN = (By.CSS_SELECTOR, ".ai-panel .markdown-body")
    MSG_FILE = (By.CSS_SELECTOR, ".ai-panel .msg-file")
    DISCLAIMER = (By.CSS_SELECTOR, ".ai-panel .ai-disclaimer")

    # ---------- 输入区 ----------
    INPUT = (By.CSS_SELECTOR, ".ai-panel .footer-input textarea")
    BTN_SEND = (By.CSS_SELECTOR, ".ai-panel .send-btn")
    BTN_STOP = (By.CSS_SELECTOR, ".ai-panel .stop-btn")
    FILE_INPUT = (By.CSS_SELECTOR, ".ai-panel input[type='file']")
    ATTACH_TAG = (By.CSS_SELECTOR, ".ai-panel .attachment-tag .el-tag")

    # ---------- 历史抽屉 ----------
    DRAWER_BODY = (By.CSS_SELECTOR, ".ai-panel .drawer__list")
    HISTORY_ITEM = (By.CSS_SELECTOR, ".ai-panel .drawer__list .history-item")
    HISTORY_TITLE = (By.CSS_SELECTOR, ".history-item__title")
    HISTORY_MORE = (By.CSS_SELECTOR, ".history-item__more")
    HISTORY_EMPTY = (
        By.XPATH,
        "//div[contains(@class,'drawer__list')]//*[contains(normalize-space(),'暂无历史')]",
    )
    DROPDOWN_ITEM = (By.CSS_SELECTOR, ".el-dropdown-menu__item")

    # ---------- 弹窗 / 提示 ----------
    PREVIEW_DIALOG = (By.CSS_SELECTOR, ".file-preview-dialog")
    PREVIEW_TEXTAREA = (By.CSS_SELECTOR, ".file-preview-dialog textarea")
    PREVIEW_BTN = (
        By.XPATH,
        "//div[contains(@class,'file-preview-dialog')]//button[contains(normalize-space(),'{text}')]",
    )
    MSGBOX = (By.CSS_SELECTOR, ".el-message-box")
    MSGBOX_INPUT = (By.CSS_SELECTOR, ".el-message-box__input input")
    MSGBOX_BTN = (
        By.XPATH,
        "//div[contains(@class,'el-message-box')]//button[contains(normalize-space(),'{text}')]",
    )
    MESSAGE = (By.CSS_SELECTOR, ".el-message")

    # ===================================================================
    # 等待基础设施
    # ===================================================================
    @staticmethod
    def _wait(driver, timeout: float, poll: float = 0.2) -> WebDriverWait:
        return WebDriverWait(driver, timeout, poll_frequency=poll, ignored_exceptions=WAIT_IGNORED)

    def _wait_bool(self, cond, timeout: float, poll: float = 0.2) -> bool:
        try:
            return bool(self._wait(self.driver, timeout, poll).until(cond))
        except TimeoutException:
            return False

    @staticmethod
    def _safe_displayed(el) -> bool:
        try:
            return bool(el.is_displayed())
        except Exception:
            return False

    @staticmethod
    def _txt(el) -> str:
        try:
            return " ".join((el.text or "").split())
        except Exception:
            return ""

    def _visible(self, locator, timeout: float = 0) -> list:
        def _probe(d):
            items = [e for e in d.find_elements(*locator) if self._safe_displayed(e)]
            return items or False

        if not timeout:
            return [e for e in self.driver.find_elements(*locator) if self._safe_displayed(e)]
        try:
            return self._wait(self.driver, timeout).until(_probe)
        except TimeoutException:
            return []

    def wait_visible(self, locator, timeout: int = 20, tag: str = ""):
        items = self._visible(locator, timeout=timeout)
        if not items:
            self.dump(tag=f"等不到「{tag or locator}」")
            raise AssertionError(f"等「{tag or locator}」可见超时（{timeout}s）")
        return items[0]

    def wait_gone(self, locator, timeout: int = 20, tag: str = "") -> bool:
        def _gone(d):
            return not [e for e in d.find_elements(*locator) if self._safe_displayed(e)]

        ok = self._wait_bool(_gone, timeout, poll=0.2)
        if not ok:
            self.dump(tag=f"「{tag or locator}」迟迟不消失")
        return ok

    def _click_el(self, el) -> None:
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        except Exception:
            pass
        try:
            el.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", el)

    def click(self, locator, timeout: int = 20, tag: str = "") -> None:
        self._click_el(self.wait_visible(locator, timeout=timeout, tag=tag))

    # ===================================================================
    # 面板开关
    # ===================================================================
    def open(self, timeout: int = 20) -> None:
        """打开面板。已打开则什么都不做。"""
        if self.is_open():
            print("[AI-UI] 面板已打开，跳过")
            return
        self.click(self.FAB, timeout=timeout, tag="悬浮球")
        self.wait_visible(self.PANEL, timeout=timeout, tag="AI 面板")
        # 打开后前端会 fetchSessions，首屏要么欢迎语，要么历史消息
        self._wait_bool(
            lambda d: bool(self._visible(self.WELCOME)) or not bool(self._visible(self.MESSAGES)),
            6,
        )
        print(f"[AI-UI] ✅ 面板已打开，标题={self.header_title()!r}")

    def close(self, timeout: int = 15) -> None:
        if not self.is_open():
            return
        self.click(self.BTN_CLOSE, timeout=timeout, tag="关闭按钮")
        assert self.wait_gone(self.PANEL, timeout=timeout, tag="AI 面板"), \
            "点了关闭按钮，`.ai-panel` 仍在显示"
        print("[AI-UI] ✅ 面板已关闭")

    def is_open(self) -> bool:
        return any(self._safe_displayed(e) for e in self.driver.find_elements(*self.PANEL))

    def header_title(self) -> str:
        items = self._visible(self.HEADER_TITLE)
        return self._txt(items[0]) if items else ""

    def panel_size(self) -> tuple:
        els = self._visible(self.PANEL)
        if not els:
            return (0, 0)
        rect = self.driver.execute_script(
            "const r = arguments[0].getBoundingClientRect();"
            "return {w: Math.round(r.width), h: Math.round(r.height)};",
            els[0],
        )
        return (rect["w"], rect["h"])

    def wait_panel_width(self, expected: int, timeout: int = 10, tol: int = 2) -> int:
        """等面板宽度收敛到期望值（±tol），返回收敛后的宽度。

        面板开合/最大化都是 CSS 过渡动画，点完立刻读会读到动画中间值
        （实测最大化过程中就抓到过 799 这种非终值），必须等宽度停下来。
        """
        self._wait_bool(
            lambda d: abs(self.panel_size()[0] - int(expected)) <= tol, timeout
        )
        return self.panel_size()[0]

    def wait_panel_width_stable(self, timeout: int = 10, poll: float = 0.2,
                                need: int = 3) -> int:
        """连续 need 次采样宽度都相同才算稳定，返回稳定宽度。纯轮询，不睡眠。"""

        class _Stable:
            def __init__(self) -> None:
                self.last = None
                self.same = 0

            def __call__(self, _driver) -> bool:
                width = self_ref.panel_size()[0]
                if width == self.last:
                    self.same += 1
                else:
                    self.last, self.same = width, 1
                return self.same >= need

        self_ref = self
        WebDriverWait(self.driver, timeout, poll).until(_Stable())
        return self.panel_size()[0]

    def maximize(self) -> tuple:
        """点最大化，等宽度真正稳定后返回放大后的尺寸。"""
        before = self.panel_size()[0]
        self.click(self.BTN_MAXIMIZE, timeout=10, tag="最大化按钮")
        self._wait_bool(lambda d: self.panel_size()[0] > before, 5)
        self.wait_panel_width_stable()
        return self.panel_size()

    def restore(self, expected_width: int) -> tuple:
        """再点同一个按钮还原，等到宽度回到 expected_width 才返回。"""
        self.click(self.BTN_MAXIMIZE, timeout=10, tag="还原按钮")
        self.wait_panel_width(expected_width)
        return self.panel_size()

    # ===================================================================
    # 输入 / 发送
    # ===================================================================
    def _input_el(self):
        els = self._visible(self.INPUT, timeout=10)
        assert els, "找不到输入框（.footer-input textarea）"
        return els[0]

    def type_message(self, text: str) -> None:
        """原生 setter + input 事件，绕开 Vue 对 selenum send_keys 的慢路径，并读回校验。"""
        el = self._input_el()
        self.driver.execute_script(
            """
            const el = arguments[0], v = arguments[1];
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLTextAreaElement.prototype, 'value').set;
            setter.call(el, v);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            """,
            el, text,
        )
        assert self.input_value() == text, f"输入框没写入成功：{self.input_value()!r}"

    def input_value(self) -> str:
        """textarea 上 .value 不是 WebElement 的属性，必须走 get_attribute。"""
        return self._input_el().get_attribute("value") or ""

    def clear_input(self) -> None:
        el = self._input_el()
        el.clear()
        if self.input_value():
            self.type_message("")

    def press_enter(self) -> None:
        self._input_el().send_keys(Keys.ENTER)

    def press_shift_enter(self) -> None:
        self._input_el().send_keys(Keys.SHIFT, Keys.ENTER)

    def is_send_disabled(self) -> bool:
        els = self._visible(self.BTN_SEND)
        if not els:
            return True
        return not els[0].is_enabled()

    def wait_send_enabled(self, timeout: int = 10) -> bool:
        return self._wait_bool(
            lambda d: bool([e for e in d.find_elements(*self.BTN_SEND)
                            if self._safe_displayed(e) and e.is_enabled()]),
            timeout,
        )

    def wait_send_btn_back(self, timeout: int = 15) -> bool:
        """等发送按钮重新出现（停止按钮消失、生成结束）。

        注意 v-if 的语义是 `!isGenerating`，`:disabled` 是 `!input.trim()`，
        发完消息输入框已被清空，所以按钮「回来了」时天然是 disabled，
        不能用 wait_send_enabled 当收敛条件。
        """
        return self._wait_bool(lambda d: bool(self._visible(self.BTN_SEND)), timeout)

    def wait_send_disabled(self, timeout: int = 10) -> bool:
        """等「发送按钮存在但变灰」（输入被清空后 Element Plus 会异步更新 disabled）。"""
        def _disabled(d):
            els = [e for e in d.find_elements(*self.BTN_SEND) if self._safe_displayed(e)]
            return bool(els) and not els[0].is_enabled()

        return self._wait_bool(_disabled, timeout)

    def type_keys(self, text: str) -> None:
        """真键盘输入（走 composition 之外的原生路径），用于 Enter / Shift+Enter 场景。"""
        self._input_el().send_keys(text)

    def send(self, text: str, timeout: int = 20) -> None:
        """填内容 + 点发送按钮，并等用户气泡出现。"""
        before = self.count_user_rows()
        self.type_message(text)
        assert self.wait_send_enabled(timeout=5), "输入了内容，发送按钮仍是 disabled"
        self.click(self.BTN_SEND, timeout=timeout, tag="发送按钮")
        assert self._wait_bool(lambda d: self.count_user_rows() > before, timeout), \
            f"点了发送，用户气泡没有新增（当前 {self.count_user_rows()} 条）"
        print(f"[AI-UI] ✅ 已发送：{text[:20]!r}")

    def is_generating(self) -> bool:
        return any(self._safe_displayed(e) for e in self.driver.find_elements(*self.BTN_STOP))

    def wait_generating(self, timeout: int = 10) -> bool:
        """等进入生成态（出现「停止」按钮）。模型很快时不一定会观察到。"""
        return self._wait_bool(lambda d: self.is_generating(), timeout)

    def wait_reply_finished(self, timeout: int = 90) -> str:
        """等回复结束：思考态消失 + markdown 渲染出现且非空 + 发送按钮复现。"""

        def _done(d):
            if [e for e in d.find_elements(*self.THINKING) if self._safe_displayed(e)]:
                return False
            if self.is_generating():
                return False
            md = [e for e in d.find_elements(*self.MARKDOWN) if self._safe_displayed(e)]
            return md and len(self._txt(md[-1])) > 0

        started = time.time()
        ok = self._wait_bool(_done, timeout, poll=0.3)
        elapsed = time.time() - started
        if not ok:
            self.dump(tag="等待回复结束超时")
            raise AssertionError(
                f"等待 AI 回复完成超时（{timeout}s，已等 {elapsed:.0f}s）："
                f"思考态={len(self._visible(self.THINKING))}，"
                f"markdown={len(self._visible(self.MARKDOWN))}，"
                f"仍在生成={self.is_generating()}"
            )
        print(f"[AI-UI] ✅ 回复完成，耗时 {elapsed:.1f}s")
        return self.last_reply_text()

    def stop_generating(self, timeout: int = 20) -> None:
        self.click(self.BTN_STOP, timeout=timeout, tag="停止按钮")
        assert self.wait_gone(self.BTN_STOP, timeout=timeout, tag="停止按钮"), \
            "点了停止，按钮仍在"
        self.wait_gone(self.THINKING, timeout=timeout, tag="思考态")
        print("[AI-UI] ✅ 已停止生成")

    # ===================================================================
    # 消息断言辅助
    # ===================================================================
    def count_user_rows(self) -> int:
        return len(self._visible(self.ROW_USER))

    def count_ai_rows(self) -> int:
        return len(self._visible(self.ROW_AI))

    def welcome_visible(self) -> bool:
        return bool(self._visible(self.WELCOME))

    def last_reply_text(self) -> str:
        md = self._visible(self.MARKDOWN)
        return self._txt(md[-1]) if md else ""

    def last_user_text(self) -> str:
        texts = self.all_user_texts()
        return texts[-1] if texts else ""

    def wait_last_user_text_not(self, text: str, timeout: int = 9) -> bool:
        """等最后一条用户气泡不再是 text（切换会话后消息区换掉的那一刻）。"""
        return self._wait_bool(lambda d: text not in self.last_user_text(), timeout)

    def wait_user_text(self, text: str, timeout: int = 20, last_only: bool = False) -> bool:
        """等用户气泡里出现指定文案；last_only=True 时只看最后一条（切换会话够用）。"""
        def _hit(d):
            texts = self.all_user_texts()
            if not texts:
                return False
            return text in (texts[-1] if last_only else " ".join(texts))

        return self._wait_bool(_hit, timeout)

    def all_user_texts(self) -> list:
        out = []
        for row in self._visible(self.ROW_USER):
            try:
                out.append(self._txt(row))
            except Exception:
                continue
        return out

    def message_area_text(self) -> str:
        items = self._visible(self.MESSAGES)
        return self._txt(items[0]) if items else ""

    def thinking_visible(self) -> bool:
        return bool(self._visible(self.THINKING))

    def disclaimer_visible(self) -> bool:
        return bool(self._visible(self.DISCLAIMER))

    def markdown_count(self) -> int:
        return len(self._visible(self.MARKDOWN))

    def has_msg_file_card(self, keyword: str = "参考文件") -> bool:
        """用户气泡里是否已有「参考文件」卡片（附件随消息发出的可见证据）。"""
        return any(keyword in self._txt(c) for c in self._visible(self.MSG_FILE))

    def wait_msg_file_card(self, timeout: int = 20, keyword: str = "参考文件") -> bool:
        """等用户气泡里出现「参考文件」卡片（附件随消息发出的可见证据）。"""
        return self._wait_bool(lambda d: self.has_msg_file_card(keyword), timeout)

    def wait_user_count(self, min_count: int, timeout: int = 20) -> bool:
        """等用户气泡数量达到 min_count（Enter 发送这类不确定点的收敛条件）。"""
        return self._wait_bool(lambda d: self.count_user_rows() >= min_count, timeout)

    # ===================================================================
    # 新对话 / 历史
    # ===================================================================
    def start_fresh_session(self, timeout: int = 20) -> None:
        """点「新对话」并等欢迎语出现。不校验 toast —— 面板刚打开、本来就是新会话时不会弹。"""
        self.click(self.BTN_NEW, timeout=timeout, tag="新对话按钮")
        assert self._wait_bool(lambda d: self.welcome_visible(), timeout), \
            "点了新对话，欢迎语没有回来（消息区没清空）"

    def new_chat(self, timeout: int = 20) -> None:
        self.click(self.BTN_NEW, timeout=timeout, tag="新对话按钮")
        self.wait_toast("已开启新对话", timeout=timeout)
        assert self._wait_bool(lambda d: self.welcome_visible(), timeout), \
            "点了新对话，欢迎语没有回来（消息区没清空）"

    def open_history(self, timeout: int = 20) -> None:
        if bool(self._visible(self.HISTORY_ITEM)):
            return
        self.click(self.BTN_HISTORY, timeout=timeout, tag="历史记录按钮")
        def _ready(d):
            return bool(self._visible(self.HISTORY_ITEM)) or bool(self._visible(self.HISTORY_EMPTY))
        assert self._wait_bool(_ready, timeout), "历史抽屉没打开（既没有条目也没有空态）"

    def close_history(self, timeout: int = 15) -> None:
        self.click(self.BTN_HISTORY, timeout=timeout, tag="历史记录按钮（再点一次收起）")
        self.wait_gone(self.HISTORY_ITEM, timeout=timeout, tag="历史条目")

    def history_open(self) -> bool:
        return bool(self._visible(self.HISTORY_ITEM)) or bool(self._visible(self.HISTORY_EMPTY))

    def history_count(self) -> int:
        return len(self._visible(self.HISTORY_ITEM))

    def history_titles(self) -> list:
        out = []
        for item in self._visible(self.HISTORY_ITEM):
            try:
                out.append(self._txt(item.find_element(*self.HISTORY_TITLE)))
            except Exception:
                out.append("")
        return out

    def history_active_titles(self) -> list:
        """当前高亮（.history-item--active）的会话标题。"""
        out = []
        for item in self._visible(self.HISTORY_ITEM):
            try:
                cls = item.get_attribute("class") or ""
                if "history-item--active" in cls:
                    out.append(self._txt(item.find_element(*self.HISTORY_TITLE)))
            except Exception:
                continue
        return out

    def wait_history_first(self, title: str, timeout: int = 10) -> bool:
        """等排序刷新后某条会话排到第一（置顶、新建会话后都用它）。"""
        def _first(d):
            items = [e for e in d.find_elements(*self.HISTORY_ITEM) if self._safe_displayed(e)]
            if not items:
                return False
            try:
                return self._txt(items[0].find_element(*self.HISTORY_TITLE)) == title
            except Exception:
                return False

        return self._wait_bool(_first, timeout)

    def _item_by_title(self, title: str, timeout: int = 15) -> str:
        """按标题精确匹配历史条目的 XPath（标题元素可能是 span 也可能是 div）。"""
        return (
            "//div[contains(@class,'ai-panel')]//div[contains(@class,'history-item')]"
            f"[.//*[contains(@class,'history-item__title') and normalize-space()=\"{title}\"]]"
        )

    def active_item(self):
        """当前高亮（.history-item--active）的条目元素；没有则返回 None。"""
        for item in self._visible(self.HISTORY_ITEM):
            if "history-item--active" in (item.get_attribute("class") or ""):
                return item
        return None

    def active_title(self) -> str:
        item = self.active_item()
        if item is None:
            return ""
        try:
            return self._txt(item.find_element(*self.HISTORY_TITLE))
        except Exception:
            return ""

    def rename_active(self, new_title: str, timeout: int = 20) -> str:
        """重命名当前会话。

        必须按 active 定位：点「新对话」建出来的会话标题都停在占位文案上，
        历史里会出现多条同名条目，按标题/下标都可能选中别人。
        """
        item = self.active_item()
        assert item is not None, "历史抽屉里没有高亮的当前会话"
        old_title = self._txt(item.find_element(*self.HISTORY_TITLE))
        self._open_element_menu(item, timeout=timeout)
        self.choose_menu("重命名", timeout=timeout)
        self._fill_prompt(new_title, timeout=timeout)
        self.click((By.XPATH, self.MSGBOX_BTN[1].format(text="确定")), timeout=timeout, tag="确定按钮")
        self.wait_toast("已重命名", timeout=timeout)
        print(f"[AI-UI] ✅ 重命名当前会话：{old_title!r} → {new_title!r}")
        return old_title

    def index_of_title(self, title: str, timeout: int = 15) -> int:
        titles = self.history_titles()
        assert title in titles, f"历史里没有标题为「{title}」的会话，当前：{titles}"
        return titles.index(title)

    def click_history_title(self, title: str, timeout: int = 20) -> None:
        """点标题对应的历史条目。优先 XPath 精确匹配，匹配不到再退回按标题算下标。"""
        locator = (By.XPATH, self._item_by_title(title))
        try:
            self.click(locator, timeout=timeout, tag=f"历史条目「{title}」")
        except Exception:
            self.click_history_at(self.index_of_title(title), timeout=timeout)

    def rename_title(self, old_title: str, new_title: str, timeout: int = 20) -> None:
        """按标题重命名，不按下标 —— 下标会被「置顶 / 用户已有会话」打乱。"""
        self.rename_at(self.index_of_title(old_title), new_title, timeout=timeout)

    def delete_title(self, title: str, timeout: int = 20) -> None:
        self.delete_at(self.index_of_title(title), timeout=timeout)

    def pin_title(self, title: str, timeout: int = 20) -> None:
        self.pin_at(self.index_of_title(title), timeout=timeout)

    def click_history_at(self, index: int, timeout: int = 20) -> str:
        items = self._visible(self.HISTORY_ITEM, timeout=timeout)
        assert items, "历史抽屉里没有会话条目"
        assert index < len(items), f"历史条目只有 {len(items)} 条，取不到第 {index + 1} 条"
        title = self._txt(items[index].find_element(*self.HISTORY_TITLE))
        self._click_el(items[index])
        # 点成功后有两个可观察结果：抽屉收起，或该条变成 active（是否收起交给用例断言）
        self._wait_bool(
            lambda d: (not self.history_open()) or (title in self.history_active_titles()),
            timeout,
        )
        return title

    def _open_element_menu(self, item, timeout: int = 15) -> None:
        """hover 某条目 → 点更多（.history-item__more 默认 opacity:0，必须 hover）。"""
        ActionChains(self.driver).move_to_element(item).perform()
        self._wait_bool(
            lambda d: bool([e for e in item.find_elements(*self.HISTORY_MORE)
                            if self._safe_displayed(e)]),
            5,
        )
        more = item.find_element(*self.HISTORY_MORE)
        self._click_el(more)

    def _open_item_menu(self, index: int, timeout: int = 15) -> None:
        items = self._visible(self.HISTORY_ITEM, timeout=timeout)
        assert items and index < len(items), f"历史条目不足（{len(items)} 条），取不到第 {index + 1} 条"
        self._open_element_menu(items[index], timeout=timeout)

    def choose_menu(self, text: str, timeout: int = 15) -> None:
        locator = (
            By.XPATH,
            f"//ul[contains(@class,'el-dropdown-menu')]"
            f"//li[contains(normalize-space(),'{text}')]",
        )
        self.click(locator, timeout=timeout, tag=f"下拉项「{text}」")

    def _fill_prompt(self, text: str, timeout: int = 20) -> None:
        """给 ElMessageBox.prompt 的输入框填值。

        坑：prompt 默认用旧标题预填，而 WebElement.clear() 对 Element Plus 的
        el-input 不生效（Vue 会把旧值同步回来），直接 send_keys 会变成
        「旧标题 + 新标题」的拼接。这里用全选 + 输入真实按键，读完再校验一次。
        """
        box = self.wait_visible(self.MSGBOX, timeout=timeout, tag="重命名弹窗")
        el = box.find_element(*self.MSGBOX_INPUT)
        el.click()
        el.send_keys(Keys.CONTROL, "a")
        el.send_keys(Keys.DELETE)
        if self._input_text_of(el):
            self.driver.execute_script(
                """
                const el = arguments[0], v = arguments[1];
                const setter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value').set;
                setter.call(el, '');
                el.dispatchEvent(new Event('input', { bubbles: true }));
                setter.call(el, v);
                el.dispatchEvent(new Event('input', { bubbles: true }));
                """,
                el, text,
            )
        else:
            el.send_keys(text)
        got = self._input_text_of(el)
        assert got == text, f"重命名输入框没填对：{got!r}（期望 {text!r}）"

    @staticmethod
    def _input_text_of(el) -> str:
        return el.get_attribute("value") or ""

    def rename_at(self, index: int, new_title: str, timeout: int = 20) -> str:
        """重命名第 index 条会话，返回修改前的标题。"""
        old = self.history_titles()[index]
        self._open_item_menu(index, timeout=timeout)
        self.choose_menu("重命名", timeout=timeout)
        self._fill_prompt(new_title, timeout=timeout)
        self.click((By.XPATH, self.MSGBOX_BTN[1].format(text="确定")), timeout=timeout, tag="确定按钮")
        self.wait_toast("已重命名", timeout=timeout)
        print(f"[AI-UI] ✅ 重命名：{old!r} → {new_title!r}")
        return old

    def pin_at(self, index: int, timeout: int = 20) -> None:
        self._open_item_menu(index, timeout=timeout)
        self.choose_menu("置顶", timeout=timeout)

    def delete_at(self, index: int, timeout: int = 20) -> str:
        """删除第 index 条会话，返回被删的标题。"""
        title = self.history_titles()[index]
        self._open_item_menu(index, timeout=timeout)
        self.choose_menu("删除", timeout=timeout)
        self.wait_visible(self.MSGBOX, timeout=timeout, tag="删除确认弹窗")
        self.click((By.XPATH, self.MSGBOX_BTN[1].format(text="删除")), timeout=timeout, tag="删除确认按钮")
        self.wait_gone(
            (By.XPATH, f"//div[contains(@class,'drawer__list')]"
                       f"//span[contains(@class,'history-item__title') and normalize-space()='{title}']"),
            timeout=timeout, tag=f"历史条目「{title}」",
        )
        print(f"[AI-UI] ✅ 已删除会话「{title}」")
        return title

    # ===================================================================
    # 附件
    # ===================================================================
    def upload_attachment(self, file_path: str, timeout: int = 40) -> str:
        """通过 el-upload 的隐藏 input 选文件，等附件 tag 出现。"""
        path = os.path.abspath(file_path)
        assert os.path.isfile(path), f"附件不存在：{path}"
        name = os.path.basename(path)
        inputs = self.driver.find_elements(*self.FILE_INPUT)
        assert inputs, "找不到 el-upload 的 file input"
        inputs[0].send_keys(path)
        assert self._wait_bool(
            lambda d: bool([e for e in d.find_elements(*self.ATTACH_TAG) if self._safe_displayed(e)]),
            timeout,
        ), f"选了 {name}，附件标签没出现（/upload-temp 可能失败）"
        got = self._txt(self._visible(self.ATTACH_TAG)[0])
        print(f"[AI-UI] ✅ 附件已就绪：{got!r}")
        return got

    def attachment_name(self) -> str:
        els = self._visible(self.ATTACH_TAG)
        return self._txt(els[0]) if els else ""

    def clear_attachment(self) -> None:
        tag = self.wait_visible(self.ATTACH_TAG, timeout=10, tag="附件标签")
        close = tag.find_element(By.CSS_SELECTOR, ".el-tag__close")
        self._click_el(close)
        self.wait_gone(self.ATTACH_TAG, timeout=10, tag="附件标签")

    def click_msg_file(self, timeout: int = 20) -> None:
        self.click(self.MSG_FILE, timeout=timeout, tag="消息里的参考文件卡片")

    def preview_text(self, timeout: int = 20) -> str:
        self.wait_visible(self.PREVIEW_DIALOG, timeout=timeout, tag="文件预览弹窗")
        els = self._visible(self.PREVIEW_TEXTAREA)
        assert els, "预览弹窗里没有 textarea"
        return els[0].get_attribute("value") or ""

    def close_preview(self, timeout: int = 15) -> None:
        self.click((By.XPATH, self.PREVIEW_BTN[1].format(text="关闭")), timeout=timeout, tag="预览弹窗关闭")
        self.wait_gone(self.PREVIEW_DIALOG, timeout=timeout, tag="文件预览弹窗")

    # ===================================================================
    # Toast / 诊断
    # ===================================================================
    def wait_toast(self, keyword: str, timeout: int = 20) -> str:
        def _match(d):
            for m in d.find_elements(*self.MESSAGE):
                if self._safe_displayed(m) and keyword in self._txt(m):
                    return self._txt(m)
            return False

        try:
            text = self._wait(self.driver, timeout, poll=0.15).until(_match)
        except TimeoutException:
            seen = [self._txt(m) for m in self.driver.find_elements(*self.MESSAGE)
                    if self._safe_displayed(m)]
            raise AssertionError(f"没等到提示「{keyword}」，当前提示：{seen}")
        print(f"[AI-UI] ✅ 提示：{text}")
        return text

    def dump(self, tag: str = "") -> None:
        """失败时把面板关键状态打出来，省掉再跑一轮看截图。"""
        try:
            panel = self.panel_size()
            print(f"[AI-UI][DUMP] {tag} | 面板={panel} | 打开={self.is_open()}")
            print(f"[AI-UI][DUMP] 用户气泡={self.count_user_rows()} AI气泡={self.count_ai_rows()} "
                  f"思考态={len(self._visible(self.THINKING))} 生成中={self.is_generating()} "
                  f"markdown={len(self._visible(self.MARKDOWN))}")
            print(f"[AI-UI][DUMP] 历史条目={self.history_titles()}")
            print(f"[AI-UI][DUMP] 消息区文本={self.message_area_text()[:200]!r}")
        except Exception as e:
            print(f"[AI-UI][DUMP] 诊断输出本身失败：{type(e).__name__}: {e}")
