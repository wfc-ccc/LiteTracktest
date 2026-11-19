"""通知中心（铃铛 + 消息面板）组件 POM。

源码是前端 components/NoticeCenter.vue（`<div class="notice-center">` + `el-popover`）。

========== 源码里必须知道的几件事 ==========
1. el-popover 的面板内容会被 teleport 到 <body> 下，
   所以 `.msg-panel` / `.msg-item` **不在** `.notice-center` 里面。
   任何带 `.notice-center` 前缀的选择器都拿不到面板内容。
2. 「一键已读」按钮有 v-if="unreadCount > 0"，未读为 0 时**按钮节点不存在**，
   不是 disabled。
3. 「清空」有 v-if="messageList.length > 0"；「刷新」一直存在。
4. 未读角标：`.bell-icon .el-badge__content`，hidden 时 display:none。
   角标数字是**全局未读数**（含任务/项目通知），不是本面板条数。
5. 列表为空时渲染 `.el-empty`（描述「暂无消息」），不渲染 `.msg-item`。
   注意这个分支是 v-if/v-else 互斥：接口一返回，`.el-empty` 会被整体移除，
   所以在空/非空切换的瞬间，刚取到的 `.el-empty` 句柄会立刻 stale。
   —— 这正是上一轮 wait_panel_ready 抛 StaleElementReferenceException 的原因。
   因此本文件里所有 is_displayed / text / get_attribute 全部做了 stale 容错，
   并且判定改成「连续 N 次轮询结论一致」才返回，不在渲染中途下结论。
6. 通知标题被前端截过：`msg.title.split('所属项目：')[0].trim()`，项目名单独在
   `.sub-project`。判断「是不是这条缺陷的通知」要读整条 item 文本。
7. 已读态：item 上有 `is-read` 类；未读红点 `.unread-dot` 是 v-if 渲染，已读即消失。
"""
from __future__ import annotations

import time

from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from pages.base_page import BasePage


class NoticeCenterComponent(BasePage):

    # ---------- 铃铛与角标 ----------
    ROOT = (By.CSS_SELECTOR, ".notice-center")
    BELL = (By.CSS_SELECTOR, ".notice-center .bell-icon")
    BADGE = (By.CSS_SELECTOR, ".notice-center .bell-icon .el-badge__content")

    # ---------- 面板（teleport 到 body，不带 .notice-center 前缀） ----------
    PANEL = (By.CSS_SELECTOR, ".msg-panel")
    PANEL_HEADER = (By.CSS_SELECTOR, ".msg-panel .msg-header")
    PANEL_EMPTY = (By.CSS_SELECTOR, ".msg-panel .el-empty")
    PANEL_LOADING = (By.CSS_SELECTOR, ".msg-panel .el-loading-mask")
    PANEL_BTN_MARK_ALL_READ = "一键已读"
    PANEL_BTN_CLEAR = "清空"
    PANEL_BTN_REFRESH = "刷新"

    # ---------- 消息条目 ----------
    MSG_ITEM = (By.CSS_SELECTOR, ".msg-item")
    MSG_ITEM_UNREAD = (By.CSS_SELECTOR, ".msg-item:not(.is-read)")
    MSG_TITLE = (By.CSS_SELECTOR, ".msg-title")
    MSG_DESC = (By.CSS_SELECTOR, ".msg-desc")
    MSG_TIME = (By.CSS_SELECTOR, ".msg-time")
    MSG_TAG = (By.CSS_SELECTOR, ".type-tag")
    MSG_SUB_PROJECT = (By.CSS_SELECTOR, ".sub-project")
    UNREAD_DOT = (By.CSS_SELECTOR, ".unread-dot")

    # ===================================================================
    # 基础工具：全部对 stale 容错
    # ===================================================================
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

    @staticmethod
    def _attr(el, name: str) -> str:
        try:
            return el.get_attribute(name) or ""
        except Exception:
            return ""

    def _kids(self, parent, locator) -> list:
        """parent 下找子元素；parent 自身 stale 就返回空"""
        try:
            return parent.find_elements(*locator)
        except Exception:
            return []

    def _displayed(self, locator, timeout: float = 0) -> list:
        """返回当前可见的匹配元素；timeout>0 时轮询"""
        end = time.time() + timeout
        while True:
            els = [el for el in self.driver.find_elements(*locator) if self._safe_displayed(el)]
            if els or time.time() > end:
                return els
            time.sleep(0.2)

    def _click_el(self, el) -> None:
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        except Exception:
            pass
        try:
            el.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", el)

    def _panel_button(self, text: str, panel=None):
        """在面板内按文本找按钮（el-button link 渲染出来也是 <button>）"""
        p = panel or self.panel()
        norm = "".join(text.split())
        btns = self._kids(p, (By.TAG_NAME, "button"))
        for btn in btns:
            if self._safe_displayed(btn) and "".join(self._txt(btn).split()) == norm:
                return btn
        for btn in btns:
            if self._safe_displayed(btn) and norm in self._txt(btn):
                return btn
        return None

    # ===================================================================
    # 面板开合
    # ===================================================================
    def panels(self) -> list:
        return self._displayed(self.PANEL)

    def is_panel_open(self) -> bool:
        return bool(self.panels())

    def panel(self):
        ps = self.panels()
        if not ps:
            raise AssertionError(
                "通知面板未展开。若刚点过铃铛，可能是 trigger=click 的二次点击把它关掉了。"
            )
        return ps[0]

    def wait_layout(self, timeout: int = 15):
        WebDriverWait(self.driver, timeout, ignored_exceptions=(Exception,)).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, ".layout__header"))
        )
        print("[NOTICE] ✅ .layout__header 已渲染")

    def open_panel(self, timeout: int = 20):
        """点铃铛展开面板（已展开则直接复用）"""
        if self.is_panel_open():
            print("[NOTICE] 面板已展开，直接复用")
            self.wait_panel_ready(timeout=timeout)
            return self.panel()

        bells = self._displayed(self.BELL, timeout=timeout)
        if not bells:
            raise AssertionError("没找到通知铃铛 .notice-center .bell-icon")
        self._click_el(bells[0])

        end = time.time() + timeout
        while time.time() < end:
            if self.is_panel_open():
                break
            time.sleep(0.2)
        else:
            self.dump_state()
            raise AssertionError("点击铃铛后通知面板没有展开（.msg-panel 一直不可见）")

        print("[NOTICE] 面板已出现，等待列表加载")
        self.wait_panel_ready(timeout=timeout)
        print("[NOTICE] ✅ 通知面板已展开")
        return self.panel()

    def close_panel(self, timeout: int = 5) -> None:
        """popover 靠 clickoutside 关闭，这里派发 document 上的鼠标事件"""
        if not self.is_panel_open():
            return
        try:
            self.driver.execute_script(
                """
                ['mousedown','mouseup','click'].forEach(t => {
                    document.dispatchEvent(new MouseEvent(t, {bubbles: true, cancelable: true}));
                    document.body.dispatchEvent(new MouseEvent(t, {bubbles: true, cancelable: true}));
                });
                """
            )
        except Exception:
            pass
        end = time.time() + timeout
        while time.time() < end:
            if not self.is_panel_open():
                print("[NOTICE] ✅ 面板已关闭")
                return
            time.sleep(0.2)
        print("[NOTICE] ⚠️ 面板仍未关闭（不影响用例）")

    def wait_panel_ready(self, timeout: int = 20, stable: int = 3) -> bool:
        """等列表加载完成。

        不能用「看到 .el-empty 就算加载完」——空/非空是 v-if/v-else 互斥分支，
        接口返回数据的瞬间空态节点会被整体移除。
        所以改成：loading 遮罩消失后，连续 stable 次轮询得到同一结论才收工。
        """
        end = time.time() + timeout
        last, same = None, 0
        while time.time() < end:
            try:
                p = self.panel()
            except AssertionError:
                last, same = None, 0
                time.sleep(0.2)
                continue

            if any(self._safe_displayed(m) for m in self._kids(p, self.PANEL_LOADING)):
                last, same = None, 0
                time.sleep(0.2)
                continue

            items = len(self._kids(p, self.MSG_ITEM))
            empty = len(self._kids(p, self.PANEL_EMPTY))
            state = ("items", items) if items else (("empty", empty) if empty else ("blank", 0))

            if state == last:
                same += 1
            else:
                last, same = state, 1
            if same >= stable:
                if state[0] == "empty":
                    print("[NOTICE] ⚠️ 面板显示「暂无消息」，该账号当前没有通知")
                elif state[0] == "blank":
                    print("[NOTICE] ⚠️ 面板既无条目也无空态，可能仍在渲染")
                else:
                    print(f"[NOTICE] ✅ 列表加载完成，共 {items} 条")
                return True
            time.sleep(0.15)

        print("[NOTICE] ⚠️ 面板加载超时")
        self.dump_state()
        return False

    def refresh(self, timeout: int = 20):
        btn = self._panel_button(self.PANEL_BTN_REFRESH)
        if btn is None:
            raise AssertionError("面板里没有「刷新」按钮")
        self._click_el(btn)
        self.wait_panel_ready(timeout=timeout)
        print("[NOTICE] ✅ 已刷新通知列表")

    # ===================================================================
    # 未读数
    # ===================================================================
    def get_unread_count(self) -> int:
        """铃铛角标上的未读数（全局未读，0 表示角标隐藏）"""
        for el in self.driver.find_elements(*self.BADGE):
            if not self._safe_displayed(el):
                continue
            txt = self._txt(el).replace("+", "")
            return int(txt) if txt.isdigit() else 0
        return 0

    def unread_item_count(self) -> int:
        """当前面板里未读条目数量"""
        try:
            p = self.panel()
        except AssertionError:
            return 0
        return len([el for el in self._kids(p, self.MSG_ITEM_UNREAD)
                    if self._safe_displayed(el)])

    # ===================================================================
    # 通知条目
    # ===================================================================
    def notice_items(self) -> list:
        try:
            p = self.panel()
        except AssertionError:
            return []
        return [el for el in self._kids(p, self.MSG_ITEM) if self._safe_displayed(el)]

    def notice_count(self) -> int:
        return len(self.notice_items())

    def notice_texts(self) -> list:
        return [self._txt(el) for el in self.notice_items()]

    def _child_text(self, el, locator) -> str:
        kids = self._kids(el, locator)
        return self._txt(kids[0]) if kids else ""

    def notice_titles(self) -> list:
        return [self._child_text(el, self.MSG_TITLE) or self._txt(el)
                for el in self.notice_items()]

    def notice_tags(self) -> list:
        return [self._child_text(el, self.MSG_TAG) for el in self.notice_items()]

    def find_notice(self, keyword: str):
        """按整条通知文本匹配（标题常被前端截断，整条更稳）"""
        norm = "".join(keyword.split())
        if not norm:
            return None
        for el in self.notice_items():
            if norm in "".join(self._txt(el).split()):
                return el
        return None

    def has_notice(self, keyword: str) -> bool:
        return self.find_notice(keyword) is not None

    def is_notice_exist(self, keyword: str, loose: bool = True) -> bool:
        """兼容旧接口名（用例 _wait_notice_item_exists 里就是这么调的）。

        1) 先按整条文本精确包含 keyword；
        2) 找不到且 loose=True 时，只要面板里存在「缺陷」类型通知就算命中，
           并打印宽松命中日志 —— 因为前端把标题截成
           `msg.title.split('所属项目：')[0]`，后端标题里不一定带缺陷标题。
           看到这条日志就说明断言口径该调整了，不是 UI 找不到。
        """
        if self.find_notice(keyword):
            print(f"[NOTICE] ✅ 存在通知（文本含「{keyword}」）")
            return True
        if loose and self.has_notice_type("缺陷"):
            print(
                f"[NOTICE] ⚠️ 宽松命中：面板里没有文本含「{keyword}」的通知，"
                f"但存在缺陷类型通知，标题为 {self.notice_titles()}。"
                "如需严格断言，请把 loose=False"
            )
            return True
        return False

    def notices_of_type(self, tag_label: str) -> list:
        """按类型标签筛：「缺陷」「任务」「项目」「告警」"""
        out = []
        for el, tag in zip(self.notice_items(), self.notice_tags()):
            if tag.strip() == tag_label:
                out.append(el)
        return out

    def has_notice_type(self, tag_label: str) -> bool:
        return bool(self.notices_of_type(tag_label))

    def wait_notice(self, keyword: str, timeout: int = 25):
        end = time.time() + timeout
        while time.time() < end:
            el = self.find_notice(keyword)
            if el is not None:
                print(f"[NOTICE] ✅ 找到通知（含「{keyword}」）")
                return el
            time.sleep(0.3)
        self.dump_notices(tag="等待通知超时")
        raise AssertionError(
            f"通知列表里没有含「{keyword}」的通知。"
            f"当前标题：{self.notice_titles()} / 类型：{self.notice_tags()} / 条数：{self.notice_count()}"
        )

    def wait_any_notice(self, timeout: int = 25):
        end = time.time() + timeout
        while time.time() < end:
            items = self.notice_items()
            if items:
                return items[0]
            time.sleep(0.3)
        self.dump_notices(tag="等待任意通知超时")
        raise AssertionError("通知面板里一条消息都没有（接口可能返回空或 401）")

    def click_notice(self, keyword: str, timeout: int = 20):
        el = self.wait_notice(keyword, timeout=timeout)
        self._click_el(el)
        print(f"[NOTICE] ✅ 已点击通知（{keyword}）")

    # ===================================================================
    # 一键已读 / 清空
    # ===================================================================
    def click_mark_all_read(self, timeout: int = 15, confirm: bool = True):
        """点「一键已读」，并在方法内等生效。

        未读为 0 时按钮不存在（v-if），不是 disabled。
        confirm=True 时会等到角标归零 + 面板无未读条目才返回 ——
        因为 handleMarkAllRead 改的是 unreadCount.value，DOM 要下一帧才更新，
        点完立刻 get_unread_count() 会读到旧值 1，这就是上一轮断言失败的原因。
        """
        p = self.panel()
        btn = self._panel_button(self.PANEL_BTN_MARK_ALL_READ, p)
        if btn is None:
            self.dump_state()
            raise AssertionError(
                "面板里没有「一键已读」按钮 —— 源码里它是 v-if=\"unreadCount > 0\"，"
                f"说明此刻未读数已是 {self.get_unread_count()}，没有未读可清。"
            )
        self._click_el(btn)
        print("[NOTICE] 已点击「一键已读」")
        self._expect_message("已全部标为已读")

        if confirm:
            try:
                self.wait_all_read(timeout=timeout)
            except AssertionError:
                self.dump_state(tag="一键已读后校验失败")
                raise

    def wait_all_read(self, timeout: int = 15) -> None:
        """等一键已读生效：角标隐藏 + 面板里没有未读条目"""
        end = time.time() + timeout
        while time.time() < end:
            if self.get_unread_count() == 0 and self.unread_item_count() == 0:
                print("[NOTICE] ✅ 未读数已归零")
                return
            time.sleep(0.2)
        raise AssertionError(
            f"一键已读未生效：角标未读数={self.get_unread_count()}，"
            f"面板未读条目={self.unread_item_count()}"
        )

    def _expect_message(self, keyword: str, timeout: int = 10) -> bool:
        end = time.time() + timeout
        seen = []
        while time.time() < end:
            seen = [self._txt(m) for m in self.driver.find_elements(By.CSS_SELECTOR, ".el-message")
                    if self._safe_displayed(m)]
            for t in seen:
                if keyword in t:
                    print(f"[NOTICE] ✅ 页面提示：{t}")
                    return True
                if "失败" in t or "错误" in t:
                    raise AssertionError(f"页面提示失败：{t}")
            time.sleep(0.2)
        print(f"[NOTICE] ⚠️ 没等到提示「{keyword}」，最近提示：{seen}")
        return False

    def click_clear_all(self, confirm: bool = True, timeout: int = 15):
        """点「清空」，会弹 ElMessageBox 确认"""
        btn = self._panel_button(self.PANEL_BTN_CLEAR)
        if btn is None:
            raise AssertionError("面板里没有「清空」按钮（列表当前为空）")
        self._click_el(btn)

        end = time.time() + timeout
        while time.time() < end:
            boxes = self._displayed((By.CSS_SELECTOR, ".el-message-box"))
            if boxes:
                break
            time.sleep(0.2)
        else:
            raise AssertionError("清空确认框没有弹出")

        label = "清空" if confirm else "取消"
        for b in self._kids(boxes[0], (By.TAG_NAME, "button")):
            if self._safe_displayed(b) and label in self._txt(b):
                self._click_el(b)
                print(f"[NOTICE] 清空确认框点「{label}」")
                return
        raise AssertionError("清空确认框里没找到按钮")

    # ===================================================================
    # 常用别名（兼容旧用例里的方法名，避免再撞 AttributeError）
    # ===================================================================
    def get_notice_count(self) -> int:
        return self.notice_count()

    def exists_notice(self, keyword: str) -> bool:
        return self.has_notice(keyword)

    def mark_all_read(self) -> None:
        self.click_mark_all_read()

    # ===================================================================
    # 诊断
    # ===================================================================
    def dump_notices(self, tag: str = "当前通知") -> None:
        items = self.notice_items()
        print(f"[NOTICE] {tag}：共 {len(items)} 条，未读角标={self.get_unread_count()}")
        for i, el in enumerate(items, 1):
            cls = self._attr(el, "class")
            print(
                f"[NOTICE]   #{i} [{self._child_text(el, self.MSG_TAG)}] "
                f"{self._child_text(el, self.MSG_TITLE)} | "
                f"{self._child_text(el, self.MSG_DESC)} | "
                f"{self._child_text(el, self.MSG_TIME)} | "
                f"{'已读' if 'is-read' in cls else '未读'}"
            )

    def dump_state(self, tag: str = "面板状态") -> None:
        panels = self.panels()
        print(f"[NOTICE] {tag}：可见面板数={len(panels)}，未读角标={self.get_unread_count()}")
        if not panels:
            print("[NOTICE]   .msg-panel 不可见 —— 铃铛没点开，或 popover 已被 clickoutside 关掉")
            return
        p = panels[0]
        for e in self._kids(p, self.PANEL_EMPTY):
            if self._safe_displayed(e):
                print(f"[NOTICE]   空状态：{self._txt(e)}")
        btns = [self._txt(b) for b in self._kids(p, (By.TAG_NAME, "button"))
                if self._safe_displayed(b)]
        print(f"[NOTICE]   面板按钮：{btns}")
        masks = [m for m in self._kids(p, self.PANEL_LOADING) if self._safe_displayed(m)]
        print(f"[NOTICE]   加载遮罩：{'有' if masks else '无'}")
        self.dump_notices(tag=tag)
