"""用户管理页 POM。

源码是 src/views/user/UserManage.vue。
动态 form-item 识别，和 BugListPage 统一架构，自动处理 stale、el-select 挂载 body。

【本版修正】
1. 去掉全部 time.sleep：弹窗等待、下拉取值收敛、重试退避一律走 WebDriverWait，
   这是全项目硬要求。
2. search() 末尾原来是 `wait_for_element_invisible(".el-table__loading")`——
   Element Plus 的遮罩类名是 `.el-loading-mask`，那个选择器一条都匹配不到，
   等于空等。改成等真遮罩撤掉。
3. 状态列不再写死 `el-table_1_column_5`，改成按表头「状态」动态取列
   （列顺序一变，写死的下标会读到「创建时间」而静默错值）。
4. 角色下拉接受 value 或 label（QA / 测试 都行），映射收进页面对象，
   用例不用再自己维护 ROLE_ALIASES。
5. 输入框改用原生 setter + input/change 事件并做读回校验，
   避免 el.clear() 后 v-model 没同步、提交时校验报「请输入用户名」。
"""
from __future__ import annotations

import re

from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from pages.base_page import BasePage
from utils.table_utils import column_index, cell_element
from utils.waits import wait_for_element_invisible

# ============ 字段关键词（只改这里，前端文案变动不用改定位逻辑）============
KW_USERNAME = ("用户名",)
KW_PASSWORD = ("密码",)
KW_REAL_NAME = ("真实姓名",)
KW_ROLE = ("角色",)

DROPDOWN_ITEM = ".el-select-dropdown__item"
LOADING_MASK = (By.CSS_SELECTOR, ".el-loading-mask")

# 前端 UserManage.vue 的 ROLE_OPTIONS：下拉里显示的是 label，QA 是 value
ROLE_LABELS = {
    "ADMIN": "管理员",
    "PM": "项目经理",
    "DEV": "开发",
    "QA": "测试",
}
ROLE_ALIASES = {**ROLE_LABELS, **{v: v for v in ROLE_LABELS.values()}}


class UserManagePage(BasePage):
    # ================= 1. 顶部视图切换、搜索区、按钮 =================
    RADIO_NORMAL = (By.XPATH, "//label[contains(@class,'el-radio-button')]//span[contains(text(), '正常用户')]")
    RADIO_DELETED = (By.XPATH, "//label[contains(@class,'el-radio-button')]//span[contains(text(), '已删除用户')]")

    INPUT_USERNAME = (By.CSS_SELECTOR, "input[placeholder='请输入用户名']")
    SELECT_ROLE_SEARCH = (By.XPATH,
                          "//div[contains(@class,'el-form-item')][.//label[normalize-space()='角色']]"
                          "//div[contains(@class,'el-select')]")
    SELECT_STATUS_SEARCH = (By.XPATH,
                            "//div[contains(@class,'el-form-item')][.//label[normalize-space()='状态']]"
                            "//div[contains(@class,'el-select')]")

    # 按钮文字直接落在 button 里（含子 span），用 normalize-space(.) 匹配更稳
    BTN_SEARCH = (By.XPATH, "//button[contains(normalize-space(.), '查询')]")
    BTN_RESET = (By.XPATH, "//button[contains(normalize-space(.), '重置')]")
    BTN_CREATE = (By.XPATH, "//button[contains(normalize-space(.), '新建用户')]")

    # 表格行、行按钮
    ROW_BY_USERNAME = (By.XPATH, "//tr[.//td[normalize-space(.)='{username}']]")
    BTN_IN_ROW = (By.XPATH, "//tr[.//td[normalize-space(.)='{username}']]//button[contains(., '{btn_text}')]")

    # MessageBox 全局确认框
    MSG_BOX = (By.CSS_SELECTOR, ".el-message-box")
    MSG_BOX_CONFIRM = (By.CSS_SELECTOR, ".el-message-box__btns .el-button--primary")

    # ================= 2. 角色文本归一（用例可直接传 QA） =================
    @staticmethod
    def role_label(text: str) -> str:
        """QA / 测试 都归一成下拉里真实的可见文案（select_real 按可见文本匹配）。"""
        key = (text or "").strip()
        return ROLE_ALIASES.get(key.upper(), key)

    # ================= 3. 弹窗通用方法 =================
    @staticmethod
    def norm_label(text: str) -> str:
        """归一化标签：去掉空白、冒号、*、零宽空格"""
        return re.sub(r"[\s:：*＊\u200b\u00a0]", "", text or "")

    def visible_dialogs(self) -> list:
        out = []
        for d in self.driver.find_elements(By.CSS_SELECTOR, ".el-dialog"):
            try:
                if d.is_displayed():
                    out.append(d)
            except StaleElementReferenceException:
                continue
        return out

    @staticmethod
    def _dialog_title(dialog) -> str:
        try:
            title_els = dialog.find_elements(By.CSS_SELECTOR, ".el-dialog__title")
            if title_els:
                return (title_els[0].text or "").strip()
            return (dialog.text or "").strip()
        except StaleElementReferenceException:
            return ""

    def visible_dialog(self, title_keyword: str = "", timeout: float = 12):
        """等目标弹窗出现。找不到标题关键词时，退化成「当前唯一可见弹窗」。"""
        def _probe(_driver):
            dialogs = self.visible_dialogs()
            if not dialogs:
                return False
            if not title_keyword:
                return dialogs[0]
            for d in dialogs:
                if title_keyword in self._dialog_title(d):
                    return d
            return False

        try:
            return WebDriverWait(self.driver, timeout, poll_frequency=0.2).until(_probe)
        except Exception:
            dialogs = self.visible_dialogs()
            if dialogs:
                print(f"[USER] ⚠️ {timeout}s 内没等到标题含「{title_keyword}」的弹窗，"
                      f"退回当前弹窗（标题={self._dialog_title(dialogs[0])!r}）")
                return dialogs[0]
            raise AssertionError(f"未找到弹窗，关键词：{title_keyword}")

    def wait_dialogs_closed(self, timeout: float = 12) -> bool:
        def _gone(_driver):
            return not self.visible_dialogs()

        try:
            WebDriverWait(self.driver, timeout, poll_frequency=0.2).until(_gone)
            return True
        except Exception:
            titles = [self._dialog_title(d) for d in self.visible_dialogs()]
            raise AssertionError(f"{timeout}s 内弹窗仍未关闭，当前可见弹窗：{titles}")

    def form_errors(self) -> list:
        """当前弹窗里的表单校验错误（submit 没反应时最有用的信息）。"""
        out = []
        for e in self.driver.find_elements(By.CSS_SELECTOR, ".el-form-item__error"):
            try:
                if e.is_displayed():
                    t = (e.text or "").strip()
                    if t:
                        out.append(t)
            except Exception:
                continue
        return out

    def form_fields(self, scope):
        """读取 form-item，区分 select / input / textarea"""
        out = []
        counters = {"select": 0, "input": 0, "textarea": 0}
        for it in scope.find_elements(By.CSS_SELECTOR, ".el-form-item"):
            try:
                labels = it.find_elements(By.CSS_SELECTOR, ".el-form-item__label")
                label = self.norm_label(labels[0].text if labels else "")
                sels = it.find_elements(By.CSS_SELECTOR, ".el-select")
                tas = it.find_elements(By.CSS_SELECTOR, "textarea.el-textarea__inner")
                ins = it.find_elements(By.CSS_SELECTOR, "input.el-input__inner")
                if sels:
                    kind, el = "select", sels[0]
                elif tas:
                    kind, el = "textarea", tas[0]
                elif ins:
                    kind, el = "input", ins[0]
                else:
                    continue
                out.append({"label": label, "kind": kind, "kind_index": counters[kind], "el": el})
                counters[kind] += 1
            except StaleElementReferenceException:
                continue
        return out

    def find_field(self, scope, kinds, *keywords, index=None, strict=True):
        fields = [f for f in self.form_fields(scope) if f["kind"] in kinds]
        if not fields:
            if strict:
                raise AssertionError(f"无 {kinds} 字段")
            return None
        # 精确匹配
        for kw in keywords:
            k = self.norm_label(kw)
            for f in fields:
                if f["label"] == k:
                    return f
        # 包含匹配
        for kw in keywords:
            k = self.norm_label(kw)
            for f in fields:
                if k in f["label"]:
                    return f
        if index is not None:
            for f in fields:
                if f["kind_index"] == index:
                    return f
        if strict:
            raise AssertionError(f"找不到字段 {keywords}，现有字段：{[f['label'] for f in fields]}")
        return None

    # ================= 4. el-select 下拉核心逻辑 =================
    def _dropdown_panel_visible(self) -> bool:
        for css in (DROPDOWN_ITEM, ".el-select-dropdown__empty", ".el-select-dropdown"):
            for el in self.driver.find_elements(By.CSS_SELECTOR, css):
                try:
                    if el.is_displayed():
                        return True
                except StaleElementReferenceException:
                    continue
        return False

    def _wait_items(self, timeout: float = 2.0):
        """等下拉项数量连续两次采样一致（不用 sleep，避免把还没渲染完的选项点掉）。"""
        state = {"last": -1, "stable": 0}

        def _probe(_driver):
            items = [i for i in self.driver.find_elements(By.CSS_SELECTOR, DROPDOWN_ITEM)
                     if i.is_displayed()]
            if items and len(items) == state["last"]:
                state["stable"] += 1
                if state["stable"] >= 1:
                    return items
            else:
                state["stable"] = 0
            state["last"] = len(items)
            return False

        try:
            return WebDriverWait(self.driver, timeout, poll_frequency=0.15).until(_probe)
        except Exception:
            return [i for i in self.driver.find_elements(By.CSS_SELECTOR, DROPDOWN_ITEM)
                    if i.is_displayed()]

    def _dismiss_open_dropdown(self, timeout: float = 3) -> None:
        if not self._dropdown_panel_visible():
            return
        try:
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except Exception:
            pass

        def _gone(_driver):
            return not self._dropdown_panel_visible()

        try:
            WebDriverWait(self.driver, timeout, poll_frequency=0.1).until(_gone)
        except Exception:
            print("[USER] ⚠️ 下拉面板 ESC 后没有收起，继续尝试选择")

    def _click_el(self, el):
        try:
            el.click()
        except StaleElementReferenceException:
            raise
        except Exception:
            self.driver.execute_script("arguments[0].click()", el)

    @staticmethod
    def _match_item(items, option_text: str):
        target = next((i for i in items if (i.text or "").strip() == option_text), None)
        if target is not None:
            return target
        low = option_text.strip().lower()
        target = next((i for i in items if (i.text or "").strip().lower() == low), None)
        if target is not None:
            return target
        return next((i for i in items if option_text in (i.text or "")), None)

    def select_real(self, select_el, option_text: str, timeout: float = 10) -> None:
        """点开 el-select 并选中可见文本为 option_text 的选项（panel 挂在 body 上）。"""
        self._dismiss_open_dropdown()
        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", select_el)

        trigger = select_el
        wrappers = select_el.find_elements(By.CSS_SELECTOR, ".el-select__wrapper")
        if wrappers:
            trigger = wrappers[0]
        self._click_el(trigger)

        def _panel(_driver):
            return self._dropdown_panel_visible()

        WebDriverWait(self.driver, timeout, poll_frequency=0.1).until(_panel)
        items = self._wait_items()
        target = self._match_item(items, option_text)
        if target is None:
            raise AssertionError(
                f"下拉找不到选项【{option_text}】，可见选项：{[i.text.strip() for i in items]}"
            )

        # 点击重试，处理 stale
        for _ in range(3):
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", target)
                self._click_el(target)
                break
            except StaleElementReferenceException:
                items = [i for i in self.driver.find_elements(By.CSS_SELECTOR, DROPDOWN_ITEM)
                         if i.is_displayed()]
                target = self._match_item(items, option_text)
                if target is None:
                    raise

        # 校验选中：等 el-select 的文本包含目标 label
        def _selected(_driver):
            try:
                return option_text in (select_el.text or "")
            except StaleElementReferenceException:
                return False

        try:
            WebDriverWait(self.driver, 5, poll_frequency=0.2).until(_selected)
        except Exception:
            print(f"[USER] ⚠️ 下拉框文本未确认包含 {option_text!r}，"
                  f"当前文本 = {(select_el.text or '').strip()!r}")

    def select_field(self, title_keyword, *keywords, option, retries=3) -> bool:
        last_err = None
        for _ in range(retries):
            dialog = self.visible_dialog(title_keyword=title_keyword)
            field = self.find_field(dialog, ("select",), *keywords)
            try:
                self.select_real(field["el"], self.role_label(option))
                return True
            except StaleElementReferenceException as e:
                last_err = e
                print("[USER] 下拉 stale，重新定位重试")
        raise AssertionError(f"下拉选择失败：{last_err}")

    def set_text(self, el, value: str) -> None:
        """原生 setter + input/change 事件，并读回校验。

        Element Plus 输入框上 el.clear() 不一定把 v-model 同步成空，
        直接 send_keys 又可能带进旧值，所以走原生 setter + 读回确认。
        """
        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        self.driver.execute_script(
            """
            const el = arguments[0], v = arguments[1];
            const proto = el.tagName === 'TEXTAREA'
                ? window.HTMLTextAreaElement.prototype
                : window.HTMLInputElement.prototype;
            const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
            setter.call(el, v);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            """,
            el, value,
        )
        actual = (el.get_attribute("value") or "").strip()
        if actual != value.strip():
            print(f"[USER] ⚠️ JS 赋值读回不一致（{actual!r} != {value!r}），退回点击+输入")
            el.click()
            el.clear()
            el.send_keys(value)

    def set_field_text(self, title_keyword, *keywords, value, retries=2) -> bool:
        last_err = None
        for _ in range(retries):
            dialog = self.visible_dialog(title_keyword=title_keyword)
            field = self.find_field(dialog, ("input",), *keywords)
            try:
                self.set_text(field["el"], value)
                return True
            except StaleElementReferenceException as e:
                last_err = e
                print("[USER] 输入框 stale，重新定位重试")
        raise AssertionError(f"输入框填写失败：{last_err}")

    # ================= 5. 页面对外动作 =================
    def open(self) -> None:
        self.open_path("/users")
        self.visible(self.BTN_CREATE)

    def switch_view(self, mode: str) -> None:
        if mode == "normal":
            self.click(self.RADIO_NORMAL)
        elif mode == "deleted":
            self.click(self.RADIO_DELETED)
        else:
            raise ValueError("mode normal / deleted")

    def wait_loading_off(self, timeout: float = 10) -> None:
        """等表格 loading 遮罩撤掉。注意类名是 .el-loading-mask。"""
        def _gone(driver):
            masks = driver.find_elements(*LOADING_MASK)
            return all(not m.is_displayed() for m in masks)

        try:
            WebDriverWait(self.driver, timeout, poll_frequency=0.2).until(_gone)
        except Exception:
            print(f"[USER] ⚠️ 表格 loading 遮罩 {timeout}s 内没消失")

    def search(self, username: str = "", role_text: str = "", status_text: str = "") -> None:
        if username:
            el = self.visible(self.INPUT_USERNAME)
            self.set_text(el, username)
        if role_text:
            self.select_real(self.visible(self.SELECT_ROLE_SEARCH), self.role_label(role_text))
        if status_text:
            self.select_real(self.visible(self.SELECT_STATUS_SEARCH), self.role_label(status_text))
        self.click(self.BTN_SEARCH)
        self.wait_loading_off()

    def reset_search(self) -> None:
        self.click(self.BTN_RESET)
        self.wait_loading_off()

    def open_create_dialog(self):
        self.click(self.BTN_CREATE)
        return self.visible_dialog(title_keyword="新建用户")

    def fill_form(self, username: str = None, password: str = None,
                  real_name: str = None, role_text: str = None) -> None:
        """动态找字段填表；role_text 传 QA 或 测试 都可以。"""
        if username is not None:
            self.set_field_text("新建用户", *KW_USERNAME, value=username)
        if password is not None:
            self.set_field_text("新建用户", *KW_PASSWORD, value=password)
        if real_name is not None:
            self.set_field_text("新建用户", *KW_REAL_NAME, value=real_name)
        if role_text is not None:
            self.select_field("新建用户", *KW_ROLE, option=role_text)

    def submit_dialog(self) -> None:
        """点确定并等弹窗关闭。校验不通过时 submitForm 直接 return、弹窗不关。"""
        dialog = self.visible_dialog(title_keyword="新建用户")
        submit_btn = dialog.find_element(By.CSS_SELECTOR, ".el-dialog__footer .el-button--primary")
        self._click_el(submit_btn)
        try:
            self.wait_dialogs_closed()
        except AssertionError as e:
            raise AssertionError(
                f"提交后弹窗未关闭，表单校验错误：{self.form_errors()}"
                f"（未通过校验时 submitForm 会直接 return，弹窗不会关）"
            ) from e

    def click_row_action(self, username: str, btn_text: str) -> None:
        loc = (self.BTN_IN_ROW[0],
               self.BTN_IN_ROW[1].replace("{username}", username).replace("{btn_text}", btn_text))
        self.click(loc)

    def row_element(self, username: str, timeout: float = 10):
        loc = (self.ROW_BY_USERNAME[0], self.ROW_BY_USERNAME[1].replace("{username}", username))
        return self.visible(loc, timeout=timeout)

    def get_row_status(self, username: str, timeout: float = 10) -> str:
        """取该用户行「状态」列的 el-tag 文本（列号按表头动态算，不写死第 5 列）。"""
        idx = column_index(self.driver, ("状态",), fallback=5) or 5
        row = self.row_element(username, timeout=timeout)
        td = cell_element(row, idx)
        if td is None:
            raise AssertionError(f"用户「{username}」这一行没有第 {idx} 列")
        try:
            return (td.find_element(By.CSS_SELECTOR, "span.el-tag").text or "").strip()
        except Exception as e:
            raise AssertionError(f"第 {idx} 列里没找到 el-tag，单元格文本={(td.text or '')!r}") from e

    def is_action_btn_exist(self, username: str, btn_text: str) -> bool:
        loc = (self.BTN_IN_ROW[0],
               self.BTN_IN_ROW[1].replace("{username}", username).replace("{btn_text}", btn_text))
        try:
            self.visible(loc, timeout=2)
            return True
        except Exception:
            return False

    def confirm_message_box(self) -> None:
        self.visible(self.MSG_BOX)
        self.click(self.MSG_BOX_CONFIRM)
        wait_for_element_invisible(self.driver, self.MSG_BOX, timeout=10)

    def get_message_box_text(self) -> str:
        self.visible(self.MSG_BOX)
        return self.driver.find_element(By.CSS_SELECTOR, ".el-message-box__message").text.strip()
