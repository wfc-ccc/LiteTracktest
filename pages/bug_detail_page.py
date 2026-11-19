from __future__ import annotations

import os
import time

from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from pages.base_page import BasePage
from utils.waits import wait_for_first_displayed


class BugDetailPage(BasePage):

    # ================= 1. 顶部 Header 与操作区 =================
    BUG_TITLE = (By.CSS_SELECTOR, ".bug-header__title")
    STATUS_TAG = (By.CSS_SELECTOR, ".bug-header__tags .el-tag:nth-child(1)")
    SEVERITY_TAG = (By.CSS_SELECTOR, ".bug-header__tags .el-tag:nth-child(2)")
    READONLY_TIP = (By.CSS_SELECTOR, ".readonly-tip")

    # 顶部操作按钮（标记已修复、验证关闭、重新激活、重新指派）
    # 用按钮整体文本匹配：icon 和文字各是一个 span，contains(span, ...) 不可靠
    HEADER_ACTION_BTN = (
        By.XPATH,
        "//div[contains(@class,'bug-header__actions')]"
        "//button[contains(normalize-space(), '{btn_text}')]",
    )

    # ================= 2. 详情卡片与内容 =================
    CARD_BY_TITLE = (
        By.XPATH,
        "//div[contains(@class,'detail-card')]"
        "[.//div[contains(@class,'card-header')]//span[contains(., '{title}')]]",
    )

    BASE_FIELD_VALUE = (
        By.XPATH,
        "//div[contains(@class,'base-info')]"
        "//td[contains(@class,'el-descriptions__label')][contains(., '{label}')]"
        "/following-sibling::td",
    )

    CONTENT_BLOCK_BODY = (
        By.XPATH,
        "//div[contains(@class,'content-block')]"
        "[.//div[contains(@class,'content-block__title') and contains(., '{title}')]]"
        "//div[contains(@class,'content-block__body')]",
    )

    ATTACHMENT_IMAGE = (By.CSS_SELECTOR, ".attachment-images .attachment-thumb")
    ATTACHMENT_FILE = (By.CSS_SELECTOR, ".attachment-files .file-link")

    # ================= 3. 流转时间轴 =================
    TIMELINE_ITEMS = (By.CSS_SELECTOR, ".timeline-item")
    TIMELINE_ITEM_TAG = (
        By.XPATH,
        ".//div[contains(@class,'timeline-item__header')]//span[contains(@class,'el-tag')]",
    )

    # ================= 4. 弹窗 =================
    DIALOG_TITLE = (By.CSS_SELECTOR, ".el-dialog__title")

    # 这四个模板常量保留，实际填写时由 _dialog_field 限定在当前弹窗内
    DIALOG_INPUT = (
        By.XPATH,
        "//div[contains(@class,'el-dialog')]//label[contains(., '{label}')]"
        "/following-sibling::div//input",
    )
    DIALOG_TEXTAREA = (
        By.XPATH,
        "//div[contains(@class,'el-dialog')]//label[contains(., '{label}')]"
        "/following-sibling::div//textarea",
    )
    DIALOG_SELECT = (
        By.XPATH,
        "//div[contains(@class,'el-dialog')]//label[contains(., '{label}')]"
        "/following-sibling::div//div[contains(@class,'el-select')]",
    )
    DIALOG_RADIO = (
        By.XPATH,
        "//div[contains(@class,'el-dialog')]//label[contains(., '验证结果')]"
        "/following-sibling::div//label[contains(., '{text}')]",
    )

    DIALOG_FILE_INPUT = (By.CSS_SELECTOR, ".el-dialog input[type='file']")

    # ⚠️ footer 是 <footer class="el-dialog__footer">，不是 div，不能用 //div 限定
    DIALOG_FOOTER_BTN = (
        By.XPATH,
        "//*[contains(@class,'el-dialog__footer')]"
        "//button[contains(normalize-space(), '{btn_text}')]",
    )

    # ===================================================================
    # 页面初始化与读取
    # ===================================================================
    def open(self, bug_id: int) -> None:
        self.open_path(f"/bugs/{bug_id}")
        self.visible(self.BUG_TITLE)
        print(f"[BUG-DETAIL-PAGE] 已打开详情页：{self.driver.current_url}")

    def wait_detail_loaded(self, title: str = "", timeout: int = 20) -> None:
        """等详情页头部渲染；传 title 时顺便校验标题"""
        WebDriverWait(self.driver, timeout).until(
            EC.visibility_of_element_located(self.BUG_TITLE)
        )
        if title:
            WebDriverWait(self.driver, timeout).until(
                lambda d: title in (d.find_element(*self.BUG_TITLE).text or "")
            )
        print(f"[BUG-DETAIL-PAGE] ✅ 详情页已加载：{self.driver.current_url}")

    def is_readonly(self) -> bool:
        try:
            return self.visible(self.READONLY_TIP, timeout=2).is_displayed()
        except Exception:
            return False

    def get_title(self) -> str:
        return self.visible(self.BUG_TITLE).text.strip()

    def get_status(self) -> str:
        return self.visible(self.STATUS_TAG).text.strip()

    def get_severity(self) -> str:
        return self.visible(self.SEVERITY_TAG).text.strip()

    def get_base_field(self, label: str) -> str:
        loc = (self.BASE_FIELD_VALUE[0], self.BASE_FIELD_VALUE[1].replace("{label}", label))
        return self.visible(loc).text.strip()

    def get_content_block(self, title: str) -> str:
        loc = (self.CONTENT_BLOCK_BODY[0], self.CONTENT_BLOCK_BODY[1].replace("{title}", title))
        return self.visible(loc).text.strip()

    # ===================================================================
    # 顶部操作按钮
    # ===================================================================
    def is_action_exist(self, btn_text: str) -> bool:
        loc = (self.HEADER_ACTION_BTN[0], self.HEADER_ACTION_BTN[1].replace("{btn_text}", btn_text))
        try:
            self.visible(loc, timeout=2)
            return True
        except Exception:
            return False

    def available_actions(self) -> list:
        """顶部当前可见按钮文案（断言失败时打印，便于判断 assignee / 角色）"""
        return [
            (b.text or "").strip()
            for b in self.driver.find_elements(
                By.CSS_SELECTOR, ".bug-header__actions button"
            )
            if b.is_displayed()
        ]

    def click_header_action(self, btn_text: str):
        loc = (self.HEADER_ACTION_BTN[0], self.HEADER_ACTION_BTN[1].replace("{btn_text}", btn_text))
        btn = self.visible(loc, timeout=15)
        print(f"[BUG-DETAIL-PAGE] 点击顶部「{(btn.text or '').strip()}」")
        self.click(loc)
        return btn

    # ===================================================================
    # 弹窗工具：只认当前可见的那个
    # ===================================================================
    def _visible_dialog(self, keyword: str = "", timeout: float = 15):
        """返回当前可见的 dialog；keyword 用于按标题区分四大弹窗"""
        end = time.time() + timeout
        while True:
            found = []
            for d in self.driver.find_elements(By.CSS_SELECTOR, ".el-dialog"):
                try:
                    if not d.is_displayed():
                        continue
                except StaleElementReferenceException:
                    continue
                title = ""
                for el in d.find_elements(By.CSS_SELECTOR, ".el-dialog__title"):
                    title = (el.text or "").strip()
                    if title:
                        break
                if not keyword or keyword in title:
                    found.append(d)
            if found:
                return found[-1]  # 最新打开的通常在 DOM 末尾
            if time.time() > end:
                raise AssertionError(f"没有等到标题含 {keyword!r} 的可见弹窗")
            time.sleep(0.2)

    def _dialog_field(self, dialog, label: str, kind: str):
        """在指定弹窗内按 label 找输入控件（不跨弹窗）"""
        base = f".//label[contains(normalize-space(), '{label}')]/following-sibling::div"
        if kind == "textarea":
            els = dialog.find_elements(By.XPATH, base + "//textarea")
        elif kind == "input":
            els = dialog.find_elements(By.XPATH, base + "//input")
        else:  # select
            els = dialog.find_elements(By.XPATH, base + "//div[contains(@class,'el-select')]")
        if not els:
            raise AssertionError(f"弹窗内没找到字段「{label}」（{kind}）")
        return els[0]

    def _fill_dialog_input(self, label: str, value: str, dialog=None):
        dlg = dialog or self._visible_dialog()
        el = self._dialog_field(dlg, label, "input")
        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        el.click()
        el.clear()
        el.send_keys(value)
        print(f"[BUG-DETAIL-PAGE] «{label}» ← {value}")

    def _fill_dialog_textarea(self, label: str, value: str, dialog=None):
        dlg = dialog or self._visible_dialog()
        el = self._dialog_field(dlg, label, "textarea")
        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        el.click()
        el.clear()
        el.send_keys(value)
        print(f"[BUG-DETAIL-PAGE] «{label}» ← {value}")

    def _dump_page_message(self, tag: str = "页面提示"):
        """把 Element Plus 的 message / notification 文案打出来，提交失败时一眼看到原因"""
        try:
            for m in self.driver.find_elements(
                By.CSS_SELECTOR, ".el-message, .el-notification"
            ):
                if m.is_displayed():
                    print(f"[BUG-DETAIL-PAGE] {tag}：{(m.text or '').strip()}")
        except Exception:
            pass

    def _dialog_buttons(self, dialog):
        return dialog.find_elements(By.TAG_NAME, "button")

    def _wait_enabled(self, text: str, dialog, timeout: int = 15):
        """在弹窗内找可点的按钮。

        关键点：el-dialog 的 #footer 渲染成 <footer class="el-dialog__footer">，
        不是 <div>，用 //div[contains(@class,'el-dialog__footer')] 会一条都找不到，
        于是在这里空转满 15s —— 上一轮就是这么超时的。
        现在直接遍历弹窗内所有 button，按规范化文本匹配。
        """
        norm = "".join(text.split())
        end = time.time() + timeout
        diag = []
        while time.time() < end:
            diag = []
            for btn in self._dialog_buttons(dialog):
                try:
                    if not btn.is_displayed():
                        continue
                    t = "".join((btn.text or "").split())
                    cls = btn.get_attribute("class") or ""
                    diag.append(f"{t!r}(enabled={btn.is_enabled()}, loading={'is-loading' in cls})")
                    if btn.is_enabled() and (t == norm or norm in t):
                        return btn
                except StaleElementReferenceException:
                    continue
            time.sleep(0.2)

        # 弹窗内没找到 → 退到全文档的 footer（多弹窗/嵌套时兜底）
        for btn in self.driver.find_elements(
            By.XPATH, "//*[contains(@class,'el-dialog__footer')]//button"
        ):
            try:
                t = "".join((btn.text or "").split())
                if btn.is_displayed() and btn.is_enabled() and (t == norm or norm in t):
                    print(f"[BUG-DETAIL-PAGE] footer 兜底命中「{t}」")
                    return btn
            except StaleElementReferenceException:
                continue

        self._dump_page_message()
        raise AssertionError(
            f"弹窗里找不到可点的按钮「{text}」。当前弹窗内按钮：{diag}"
        )

    def _click_dialog_btn(self, btn_text: str, dialog=None, wait_closed: bool = True,
                          timeout: int = 15):
        """点 footer 按钮 → 等弹窗关闭（这一步是确认操作真的提交了）"""
        dlg = dialog or self._visible_dialog()
        btn = self._wait_enabled(btn_text, dlg, timeout=timeout)
        print(f"[BUG-DETAIL-PAGE] 点击「{btn_text}」")
        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
        try:
            btn.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", btn)

        if wait_closed:
            self._wait_dialog_closed(dlg, timeout=timeout)
        return dlg

    def _wait_dialog_closed(self, dialog, timeout: int = 15) -> None:
        """destroy-on-close 会移除节点，staleness 或不可见都视为关闭"""
        end = time.time() + timeout
        while time.time() < end:
            try:
                if not dialog.is_displayed():
                    print("[BUG-DETAIL-PAGE] ✅ 弹窗已关闭")
                    return
            except StaleElementReferenceException:
                print("[BUG-DETAIL-PAGE] ✅ 弹窗已关闭")
                return
            time.sleep(0.2)
        self._dump_page_message("提交未关闭弹窗，页面提示")
        try:
            errs = [
                e.text
                for e in dialog.find_elements(By.CSS_SELECTOR, ".el-form-item__error")
                if e.is_displayed()
            ]
        except Exception:
            errs = []
        raise AssertionError(
            f"提交后弹窗没有关闭，操作可能未生效。残留校验错误：{errs}"
        )

    def upload_dialog_attachment(self, file_path: str, dialog=None):
        dlg = dialog or self._visible_dialog()
        abs_path = os.path.abspath(file_path)
        if not os.path.isfile(abs_path):
            raise FileNotFoundError(f"附件不存在：{abs_path}")
        dlg.find_element(By.CSS_SELECTOR, "input[type='file']").send_keys(abs_path)
        print(f"[BUG-DETAIL-PAGE] 已选择附件：{abs_path}")

    def _assert_no_form_error(self, dialog) -> None:
        errs = [
            e.text
            for e in dialog.find_elements(By.CSS_SELECTOR, ".el-form-item__error")
            if e.is_displayed()
        ]
        if errs:
            raise AssertionError(f"提交前仍有校验错误，字段没填上：{errs}")

    # ===================================================================
    # 业务动作：DEV 提交修复报告
    # ===================================================================
    def submit_fix_report(
        self,
        root_cause: str,
        version: str,
        self_test: str,
        impact: str = "",
        risks: str = "",
        file_path: str = None,
        timeout: int = 15,
    ):
        self.click_header_action("标记已修复")
        dialog = self._visible_dialog("填写修复报告", timeout=timeout)

        self._fill_dialog_textarea("根因与修复说明", root_cause, dialog)
        self._fill_dialog_input("修复版本/提交", version, dialog)
        self._fill_dialog_textarea("自测结果", self_test, dialog)
        if impact:
            self._fill_dialog_textarea("影响范围/回归建议", impact, dialog)
        if risks:
            self._fill_dialog_textarea("风险/限制", risks, dialog)
        if file_path:
            self.upload_dialog_attachment(file_path, dialog)

        self._assert_no_form_error(dialog)
        self._click_dialog_btn("提交修复报告", dialog, timeout=timeout)
        print("[BUG-DETAIL-PAGE] ✅ 修复报告已提交")

    # ===================================================================
    # 业务动作：QA 验证关闭
    # ===================================================================
    def submit_qa_verification(self, result: str = "验证通过", steps: str = "",
                               file_path: str = None, timeout: int = 15):
        if "重新激活" in result or "不通过" in result:
            raise AssertionError(
                "「回归不通过」走的是打回弹窗，请改用 submit_reopen_report(...)"
            )

        self.click_header_action("验证关闭")
        dialog = self._visible_dialog("提交测试报告", timeout=timeout)

        radio_loc = (self.DIALOG_RADIO[0], self.DIALOG_RADIO[1].replace("{text}", result))
        clicked = False
        for el in self.driver.find_elements(*radio_loc):
            try:
                if el.is_displayed():
                    self.click(radio_loc)
                    clicked = True
                    break
            except StaleElementReferenceException:
                continue
        if not clicked:
            raise AssertionError(f"弹窗里没有单选「{result}」")

        self._fill_dialog_textarea("测试验证步骤", steps, dialog)
        if file_path:
            self.upload_dialog_attachment(file_path, dialog)

        self._assert_no_form_error(dialog)
        self._click_dialog_btn("提交测试报告", dialog, timeout=timeout)
        print("[BUG-DETAIL-PAGE] ✅ 测试报告已提交")

    # ===================================================================
    # 业务动作：QA 打回单
    # ===================================================================
    def submit_reopen_report(self, reason_type: str, reason_desc: str, env: str,
                             expected: str, actual: str, steps: str, timeout: int = 15):
        self.click_header_action("重新激活")
        dialog = self._visible_dialog("打回", timeout=timeout)

        self.click((self.DIALOG_SELECT[0], self.DIALOG_SELECT[1].replace("{label}", "打回原因分类")))
        opt = (
            By.XPATH,
            "//li[contains(@class,'el-select-dropdown__item')]"
            f"//span[normalize-space()='{reason_type}']",
        )
        wait_for_first_displayed(self.driver, opt).click()

        self._fill_dialog_textarea("打回详细说明", reason_desc, dialog)
        self._fill_dialog_input("验证版本与环境", env, dialog)
        self._fill_dialog_textarea("预期结果", expected, dialog)
        self._fill_dialog_textarea("实际结果", actual, dialog)
        self._fill_dialog_textarea("复现步骤与测试数据", steps, dialog)

        self._assert_no_form_error(dialog)
        self._click_dialog_btn("确认打回", dialog, timeout=timeout)
        print("[BUG-DETAIL-PAGE] ✅ 打回单已提交")

    # ===================================================================
    # 业务动作：QA / PM 重新指派
    # ===================================================================
    def reassign_bug(self, assignee_name: str, timeout: int = 15):
        self.click_header_action("重新指派")
        dialog = self._visible_dialog("重新指派", timeout=timeout)

        self.click((self.DIALOG_SELECT[0], self.DIALOG_SELECT[1].replace("{label}", "指派人")))
        opt = (
            By.XPATH,
            "//li[contains(@class,'el-select-dropdown__item')]"
            f"//span[contains(normalize-space(), '{assignee_name}')]",
        )
        wait_for_first_displayed(self.driver, opt).click()

        self._click_dialog_btn("确定", dialog, timeout=timeout)
        print(f"[BUG-DETAIL-PAGE] ✅ 已重新指派给 {assignee_name}")

    # ===================================================================
    # 流转记录断言
    # ===================================================================
    def get_timeline_actions(self) -> list:
        actions = []
        for el in self.driver.find_elements(*self.TIMELINE_ITEMS):
            try:
                tag_el = el.find_element(*self.TIMELINE_ITEM_TAG)
                actions.append((tag_el.text or "").strip())
            except Exception:
                continue
        return actions
