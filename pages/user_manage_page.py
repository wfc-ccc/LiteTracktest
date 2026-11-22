"""用户管理页 POM。
src/views/user/UserManage.vue
动态form-item识别，和BugListPage统一架构，自动处理stale、el-select挂载body
"""
from __future__ import annotations
import re
import time
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pages.base_page import BasePage
from utils.waits import wait_for_element_invisible

# ============ 字段关键词（只改这里，前端文案变动不用改定位逻辑）============
KW_USERNAME = ("用户名",)
KW_PASSWORD = ("密码",)
KW_REAL_NAME = ("真实姓名",)
KW_ROLE = ("角色",)

DROPDOWN_ITEM = ".el-select-dropdown__item"

class UserManagePage(BasePage):
    # ================= 1. 顶部视图切换、搜索区、按钮 =================
    RADIO_NORMAL = (By.XPATH, "//label[contains(@class, 'el-radio-button')]//span[contains(text(), '正常用户')]")
    RADIO_DELETED = (By.XPATH, "//label[contains(@class, 'el-radio-button')]//span[contains(text(), '已删除用户')]")

    INPUT_USERNAME = (By.CSS_SELECTOR, "input[placeholder='请输入用户名']")
    SELECT_ROLE_SEARCH = (By.XPATH,
                   "//div[contains(@class, 'el-form-item')][.//label[text()='角色']]//div[contains(@class, 'el-select')]")
    SELECT_STATUS_SEARCH = (By.XPATH,
                     "//div[contains(@class, 'el-form-item')][.//label[text()='状态']]//div[contains(@class, 'el-select')]")

    BTN_SEARCH = (By.XPATH, "//button[contains(span, '查询')]")
    BTN_RESET = (By.XPATH, "//button[contains(span, '重置')]")
    BTN_CREATE = (By.XPATH, "//button[contains(span, '新建用户')]")

    # 表格行、行按钮
    ROW_BY_USERNAME = (By.XPATH, "//tr[.//td[normalize-space(.)='{username}']]")
    BTN_IN_ROW = (By.XPATH, "//tr[.//td[normalize-space(.)='{username}']]//button[contains(., '{btn_text}')]")
    TAG_STATUS = (By.XPATH,
                  "//tr[.//td[normalize-space(.)='{username}']]/td[contains(@class, 'el-table_1_column_5')]//span[contains(@class, 'el-tag')]")

    # MessageBox 全局确认框
    MSG_BOX = (By.CSS_SELECTOR, ".el-message-box")
    MSG_BOX_CONFIRM = (By.CSS_SELECTOR, ".el-message-box__btns .el-button--primary")

    # ================= 弹窗通用方法（和BugList完全复用逻辑） =================
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

    def visible_dialog(self, title_keyword: str = "", timeout: int = 12):
        end = time.time() + timeout
        fallback, fallback_at = None, 0.0
        while True:
            dialogs = self.visible_dialogs()
            if title_keyword:
                for d in dialogs:
                    title = self._dialog_title(d)
                    if title_keyword in title:
                        return d
                if len(dialogs) == 1 and fallback is None:
                    fallback, fallback_at = dialogs[0], time.time()
                if fallback is not None and time.time() - fallback_at > 1.0:
                    return fallback
            elif dialogs:
                return dialogs[0]
            if time.time() > end:
                break
            time.sleep(0.2)
        if fallback is not None:
            return fallback
        raise AssertionError(f"未找到弹窗，关键词：{title_keyword}")

    @staticmethod
    def _dialog_title(dialog) -> str:
        try:
            title_els = dialog.find_elements(By.CSS_SELECTOR, ".el-dialog__title")
            if title_els:
                return (title_els[0].text or "").strip()
            return (dialog.text or "").strip()
        except StaleElementReferenceException:
            return ""

    def wait_dialogs_closed(self, timeout: int = 12):
        end = time.time() + timeout
        while time.time() < end:
            if not self.visible_dialogs():
                return True
            time.sleep(0.25)
        raise AssertionError("弹窗未关闭")

    def form_fields(self, scope):
        """读取form-item，区分 select / input / textarea"""
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
                counters[kind] +=1
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

    # ========== el-select 下拉核心逻辑（和BugListPage完全一致） ==========
    def _dropdown_panel_visible(self) -> bool:
        for css in (DROPDOWN_ITEM, ".el-select-dropdown__empty", ".el-select-dropdown"):
            for el in self.driver.find_elements(By.CSS_SELECTOR, css):
                try:
                    if el.is_displayed():
                        return True
                except StaleElementReferenceException:
                    continue
        return False

    def _wait_items(self, budget=1.2):
        driver = self.driver
        end = time.time() + budget
        last, stable, items = [],0,[]
        while time.time() < end:
            items = [i for i in driver.find_elements(By.CSS_SELECTOR, DROPDOWN_ITEM) if i.is_displayed()]
            if items and len(items)==len(last):
                stable +=1
                if stable >=2:
                    return items
            else:
                stable=0
            last = items
            time.sleep(0.12)
        return [i for i in driver.find_elements(By.CSS_SELECTOR, DROPDOWN_ITEM) if i.is_displayed()]

    def _dismiss_open_dropdown(self):
        if not self._dropdown_panel_visible():
            return
        try:
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            time.sleep(0.15)
        except Exception:
            pass

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
        target = next((i for i in items if option_text in (i.text or "")), None)
        return target

    def select_real(self, select_el, option_text: str, timeout=10):
        self._dismiss_open_dropdown()
        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", select_el)
        trigger = select_el
        wrappers = select_el.find_elements(By.CSS_SELECTOR, ".el-select__wrapper")
        if wrappers:
            trigger = wrappers[0]
        self._click_el(trigger)
        WebDriverWait(self.driver, timeout).until(lambda d: self._dropdown_panel_visible())
        items = self._wait_items(0.8)
        target = self._match_item(items, option_text)
        if target is None:
            raise AssertionError(f"下拉找不到选项【{option_text}】，可见选项：{[i.text.strip() for i in items]}")
        # 点击重试，处理stale
        for attempt in range(3):
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", target)
                self._click_el(target)
                break
            except StaleElementReferenceException:
                items = [i for i in self.driver.find_elements(By.CSS_SELECTOR, DROPDOWN_ITEM) if i.is_displayed()]
                target = self._match_item(items, option_text)
                if target is None:
                    raise
                time.sleep(0.2)
        # 校验选中
        try:
            WebDriverWait(self.driver,5).until(lambda d: option_text in (select_el.text or ""))
        except TimeoutException:
            print(f"⚠️ 下拉框文本未确认包含 {option_text}, 当前文本：{select_el.text}")

    def select_field(self, title_keyword, *keywords, option, retries=3):
        last_err = None
        for attempt in range(1, retries+1):
            dialog = self.visible_dialog(title_keyword=title_keyword)
            field = self.find_field(dialog, ("select",), *keywords)
            try:
                self.select_real(field["el"], option)
                return True
            except StaleElementReferenceException as e:
                last_err = e
                print(f"角色下拉stale，重试{attempt}")
                time.sleep(0.3)
        raise AssertionError(f"下拉选择失败：{last_err}")

    def set_text(self, el, value: str):
        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        el.click()
        el.clear()
        el.send_keys(value)

    def set_field_text(self, title_keyword, *keywords, value, retries=2):
        last_err = None
        for attempt in range(1, retries+1):
            dialog = self.visible_dialog(title_keyword=title_keyword)
            field = self.find_field(dialog, ("input",), *keywords)
            try:
                self.set_text(field["el"], value)
                return True
            except StaleElementReferenceException as e:
                last_err = e
                time.sleep(0.3)
        raise AssertionError(f"输入框填写失败：{last_err}")

    # ===================== 页面对外动作 =====================
    def open(self) -> None:
        self.open_path("/users")
        self.visible(self.BTN_CREATE)

    def switch_view(self, mode: str):
        if mode == "normal":
            self.click(self.RADIO_NORMAL)
        elif mode == "deleted":
            self.click(self.RADIO_DELETED)
        else:
            raise ValueError("mode normal / deleted")

    def search(self, username: str = "", role_text: str = "", status_text: str = ""):
        if username:
            el = self.visible(self.INPUT_USERNAME)
            el.clear()
            el.send_keys(username)
        if role_text:
            sel = self.visible(self.SELECT_ROLE_SEARCH)
            self.select_real(sel, role_text)
        if status_text:
            sel = self.visible(self.SELECT_STATUS_SEARCH)
            self.select_real(sel, status_text)
        self.click(self.BTN_SEARCH)
        wait_for_element_invisible(self.driver, (By.CSS_SELECTOR, ".el-table__loading"), timeout=10)

    def reset_search(self):
        self.click(self.BTN_RESET)

    def open_create_dialog(self):
        self.click(self.BTN_CREATE)
        self.visible_dialog(title_keyword="新建用户")

    def fill_form(self, username: str = None, password: str = None, real_name: str = None, role_text: str = None):
        """【重点】现在不再写死xpath，动态找字段"""
        if username is not None:
            self.set_field_text("新建用户", *KW_USERNAME, value=username)
        if password is not None:
            self.set_field_text("新建用户", *KW_PASSWORD, value=password)
        if real_name is not None:
            self.set_field_text("新建用户", *KW_REAL_NAME, value=real_name)
        if role_text is not None:
            self.select_field("新建用户", *KW_ROLE, option=role_text)

    def submit_dialog(self):
        dialog = self.visible_dialog(title_keyword="新建用户")
        submit_btn = dialog.find_element(By.CSS_SELECTOR, ".el-dialog__footer .el-button--primary")
        self._click_el(submit_btn)
        self.wait_dialogs_closed()

    def click_row_action(self, username: str, btn_text: str):
        loc = (self.BTN_IN_ROW[0], self.BTN_IN_ROW[1].replace("{username}", username).replace("{btn_text}", btn_text))
        self.click(loc)

    def get_row_status(self, username: str) -> str:
        loc = (self.TAG_STATUS[0], self.TAG_STATUS[1].replace("{username}", username))
        return self.visible(loc).text.strip()

    def is_action_btn_exist(self, username: str, btn_text: str) -> bool:
        loc = (self.BTN_IN_ROW[0], self.BTN_IN_ROW[1].replace("{username}", username).replace("{btn_text}", btn_text))
        try:
            self.visible(loc, timeout=2)
            return True
        except Exception:
            return False

    def confirm_message_box(self):
        self.visible(self.MSG_BOX)
        self.click(self.MSG_BOX_CONFIRM)
        wait_for_element_invisible(self.driver, self.MSG_BOX, timeout=10)

    def get_message_box_text(self) -> str:
        self.visible(self.MSG_BOX)
        return self.driver.find_element(By.CSS_SELECTOR, ".el-message-box__message").text.strip()
