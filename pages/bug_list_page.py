"""缺陷管理页 POM。源码：src/views/bug/BugList.vue

用法：整文件覆盖到 tests 项目的 pages/bug_list_page.py。

========== v3 定位策略 ==========

核心原则：**不缓存 WebElement**。
Vue 在表单输入 / 校验过程中会反复 patch 节点，一次收集多个元素再逐个操作必然 stale。
所以每次填字段前都重新取 dialog、重新取该字段的元素，用完即弃。

1. 字段定位 —— 字段指纹
   遍历当前可见 .el-dialog 的 .el-form-item，读 label 的 innerText，
   归一化（去空白、冒号、必填星号、零宽字符）后按「精确 → 包含」匹配。
   → 中文比对不进 XPath；「所属项目」排第一位也不影响，只认名字不认下标。
   → label 文案改了只改文件顶部的 KW_* 常量。

2. 下拉选值 —— 真交互 + stale 重试
   点开面板 →（filterable 则先输入过滤）→ 在可见的 .el-select-dropdown__item
   里精确 / 宽松匹配后点选 → 断言下拉框已显示该值。
   遇到 stale 自动重查元素重试（默认 3 次），而不是让异常冒到用例层。

3. 弹层收尾不再 remove DOM
   v1 的 popper.remove() 会让 Vue 卸载时操作已移除节点，渲染进程崩溃
   → InvalidSessionIdException。改为「只有确实存在可见下拉面板时才发 ESC」，
   避免在输入框里误触 blur 引起额外重渲染。

兼容性：
   - 对外方法签名与 v1 一致（open / search / fill_create_form / submit_create /
     open_assign_dialog / assign_to），用例不必改。
   - safe_set_el_select / safe_set_el_select_by_index / dialog_text_inputs 等旧名保留。
"""
from __future__ import annotations

import os
import re
import time

from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from pages.base_page import BasePage

# ============ 字段关键词（文案调整只改这里）============
KW_TITLE = ("缺陷标题", "标题")
KW_MODULE = ("所属模块", "模块")
KW_VERSION = ("发现版本", "版本")
KW_ENV = ("环境", "测试环境")
KW_STATUS = ("状态", "缺陷状态")
KW_PRIORITY = ("优先级", "优先")
KW_SEVERITY = ("严重程度", "严重", "级别")
KW_ASSIGNEE = ("指派给", "指派人", "负责人", "处理人")
KW_DESC = ("复现步骤", "重现步骤", "步骤")
KW_EXPECT = ("预期结果", "预期")
KW_ACTUAL = ("实际结果", "实际")

DROPDOWN_ITEM = ".el-select-dropdown__item"

# ============ 枚举文案映射（测试数据写英文，前端展示中文）============
# 按列表顺序逐个尝试，命中哪个用哪个；都命中不到会报错并打印可见选项。
OPTION_ALIASES = {
    # 优先级
    "HIGH": ["高", "紧急", "重要"],
    "MEDIUM": ["中", "中等", "一般"],
    "LOW": ["低", "轻微"],
    "URGENT": ["紧急", "高", "致命"],
    # 严重程度
    "CRITICAL": ["致命", "严重", "高"],
    "FATAL": ["致命", "严重"],
    "SERIOUS": ["严重", "较严重", "高"],
    "MAJOR": ["严重", "较严重", "高"],
    "NORMAL": ["一般", "普通", "中"],
    "MINOR": ["轻微", "一般", "低"],
    "TRIVIAL": ["建议", "提示", "轻微"],
}


class BugListPage(BasePage):

    # ================= 1. 顶部搜索区与操作 =================
    INPUT_TITLE = (By.CSS_SELECTOR, ".search-form input[placeholder*='标题']")
    SEARCH_SELECT = (
        By.XPATH,
        "//div[contains(@class,'search-form')]//label[contains(., '{label}')]"
        "/following-sibling::div//div[contains(@class,'el-select')]",
    )
    SEARCH_TOOLBAR = (By.CSS_SELECTOR, ".search-toolbar")
    SEARCH_FORM = (By.CSS_SELECTOR, ".search-form")
    BTN_SEARCH = (
        By.XPATH,
        "//div[contains(@class,'search-form')]//button["
        "contains(normalize-space(),'搜索') or contains(normalize-space(),'查询')]",
    )
    # Element Plus 把 type="primary" 渲染成 class，DOM 上没有 type='primary' 属性
    BTN_SEARCH_FALLBACK = (By.CSS_SELECTOR, ".search-form .el-button--primary")
    BTN_RESET = (
        By.XPATH,
        "//div[contains(@class,'search-form')]//button[contains(normalize-space(),'重置')]",
    )
    BTN_CREATE = (
        By.XPATH,
        "//div[contains(@class,'action-right')]//button[contains(normalize-space(), '提交缺陷')]",
    )
    OPTION_DROPDOWN = (
        By.XPATH,
        "//li[contains(@class,'el-select-dropdown__item')]//span[normalize-space()='{text}']",
    )

    # ================= 2. 表格区域 =================
    ROW_TITLE = (By.XPATH, "//tr[.//td[normalize-space(.)='{title}']]")
    ROW_ACTION_BTN = (
        By.XPATH,
        "//tr[.//td[normalize-space(.)='{title}']]//button[normalize-space(.)='{btn_text}']",
    )
    ROW_UPDATED_CLASS = (
        By.XPATH,
        "//tr[contains(@class,'bug-row--updated')][.//td[normalize-space(.)='{title}']]",
    )
    EMPTY_TEXT = (By.CSS_SELECTOR, ".el-table__empty-text")

    # ================= 3. 弹窗（通用） =================
    DIALOG_CREATE_TITLE = (
        By.XPATH,
        "//div[contains(@class,'el-dialog')]//span[normalize-space()='提交缺陷']",
    )
    DIALOG_ASSIGN_TITLE = (
        By.XPATH,
        "//div[contains(@class,'el-dialog')]//span[normalize-space()='指派缺陷']",
    )
    DIALOG_CONTENT = (By.CSS_SELECTOR, ".el-dialog__body")

    # 旧常量保留兼容；新逻辑走 form_fields 动态查询
    DIALOG_INPUTS = (By.CSS_SELECTOR, ".el-dialog__body .el-input__inner")
    DIALOG_TEXTAREAS = (By.CSS_SELECTOR, ".el-dialog__body textarea.el-textarea__inner")
    DIALOG_SELECTS = (By.CSS_SELECTOR, ".el-dialog__body .el-select")

    BTN_AI_OPTIMIZE = (
        By.XPATH,
        "//button[contains(normalize-space(),'AI') and contains(normalize-space(),'润色')]",
    )
    UPLOAD_FILE_INPUT = (By.CSS_SELECTOR, ".el-dialog input[type='file']")

    BTN_DIALOG_SUBMIT = (By.CSS_SELECTOR, ".el-dialog__footer .el-button--primary")
    BTN_DIALOG_CANCEL = (By.CSS_SELECTOR, ".el-dialog__footer .el-button--default")
    BTN_CREATE_SUBMIT = BTN_DIALOG_SUBMIT  # 兼容旧名
    BTN_CREATE_CANCEL = BTN_DIALOG_CANCEL  # 兼容旧名

    # ===================================================================
    # 0. 弹窗作用域：只认「当前可见」的 dialog
    # ===================================================================
    @staticmethod
    def _title_of(dialog) -> str:
        for css in (".el-dialog__title", ".el-dialog__header"):
            els = dialog.find_elements(By.CSS_SELECTOR, css)
            if not els:
                continue
            try:
                text = (els[0].text or "").strip()
            except StaleElementReferenceException:
                continue
            if text:
                return text
        try:
            return (dialog.text or "").strip()
        except StaleElementReferenceException:
            return ""

    def visible_dialogs(self) -> list:
        out = []
        for d in self.driver.find_elements(By.CSS_SELECTOR, ".el-dialog"):
            try:
                if d.is_displayed():
                    out.append(d)
            except StaleElementReferenceException:
                continue
        return out

    def visible_dialog(self, title_keyword: str = "", timeout: int = 15):
        """返回当前可见的 el-dialog；title_keyword 区分「提交缺陷」与「指派缺陷」"""
        end = time.time() + timeout
        fallback, fallback_at = None, 0.0
        while True:
            dialogs = self.visible_dialogs()
            if title_keyword:
                for d in dialogs:
                    if title_keyword in self._title_of(d):
                        return d
                # 只有一个弹窗但标题没匹配上：等弹窗动画结束后兜底
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
        raise AssertionError(f"未找到可见 el-dialog（title_keyword={title_keyword!r}）")

    def wait_dialogs_closed(self, timeout: int = 15, msg: str = "弹窗未关闭"):
        end = time.time() + timeout
        while time.time() < end:
            if not self.visible_dialogs():
                return True
            time.sleep(0.3)
        raise AssertionError(msg)

    # ===================================================================
    # 1. 字段收集与字段指纹定位（每次调用都重新查询，不缓存）
    # ===================================================================
    @staticmethod
    def norm_label(text: str) -> str:
        """归一化字段名：去空白、冒号、必填星号、零宽字符"""
        return re.sub(r"[\s:：*＊\u200b\u00a0]", "", text or "")

    def form_fields(self, scope) -> list:
        """
        一次性读取作用域内所有可操作字段：
        [{'label', 'kind': select|input|textarea, 'kind_index', 'el'}]
        select 优先判断（因为 select 内部也含 input，会被误判成输入框）。
        """
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
            except StaleElementReferenceException:
                continue

            out.append(
                {
                    "label": label,
                    "kind": kind,
                    "kind_index": counters[kind],
                    "el": el,
                }
            )
            counters[kind] += 1
        return out

    def find_field(self, scope, kinds, *keywords, index=None, strict=True):
        """
        在作用域内按字段名定位：精确匹配 → 包含匹配 → 同类型下标兜底。
        kinds 传 ('select',) / ('input',) / ('textarea',) 等，限定字段类型。
        """
        fields = [f for f in self.form_fields(scope) if f["kind"] in kinds]
        if not fields:
            if strict:
                raise AssertionError(f"作用域内没有 {kinds} 类型字段")
            return None

        for kw in keywords:  # 1) 精确
            k = self.norm_label(kw)
            if not k:
                continue
            for f in fields:
                if f["label"] == k:
                    print(f"[BUG-FIELD] {kw!r} → 精确命中 «{f['label']}»（{f['kind']}）")
                    return f

        for kw in keywords:  # 2) 包含
            k = self.norm_label(kw)
            if not k:
                continue
            for f in fields:
                if k in f["label"]:
                    print(f"[BUG-FIELD] {kw!r} → 包含命中 «{f['label']}»（{f['kind']}）")
                    return f

        if index is not None:  # 3) 下标兜底
            for f in fields:
                if f["kind_index"] == index:
                    print(
                        f"[BUG-FIELD] 关键词 {keywords} 未命中，退回下标 {index}"
                        f"（«{f['label']}»）"
                    )
                    return f

        if strict:
            raise AssertionError(
                f"未找到字段 {keywords}；作用域内现有字段："
                f"{[(f['kind'], f['label']) for f in self.form_fields(scope)]}"
            )
        return None

    # 兼容旧方法名
    def dialog_selects(self, dialog) -> list:
        return [f for f in self.form_fields(dialog) if f["kind"] == "select"]

    def pick_dialog_select(self, dialog, *keywords, index=None):
        return self.find_field(dialog, ("select",), *keywords, index=index)["el"]

    # ===================================================================
    # 2. 下拉真交互（不缓存元素 + stale 重试 + 远程搜索支持）
    # ===================================================================
    def _dropdown_panel_visible(self) -> bool:
        """面板可见即算打开：有选项、空状态、或下拉容器本身"""
        for css in (DROPDOWN_ITEM, ".el-select-dropdown__empty", ".el-select-dropdown"):
            for el in self.driver.find_elements(By.CSS_SELECTOR, css):
                try:
                    if el.is_displayed():
                        return True
                except StaleElementReferenceException:
                    continue
        return False

    def _has_visible_dropdown(self) -> bool:
        return self._dropdown_panel_visible()

    def _dropdown_empty_text(self) -> str:
        for el in self.driver.find_elements(By.CSS_SELECTOR, ".el-select-dropdown__empty"):
            try:
                if el.is_displayed():
                    return (el.text or "").strip()
            except StaleElementReferenceException:
                continue
        return ""

    def _select_input(self, select_el):
        """取下拉内部可输入的 input（filterable / remote 才有）"""
        try:
            for inp in select_el.find_elements(
                By.CSS_SELECTOR, "input.el-select__input, input.el-input__inner"
            ):
                if inp.is_displayed():
                    return inp
        except StaleElementReferenceException:
            return None
        return None

    def _type_filter(self, inp, text: str) -> bool:
        """往下拉输入框写过滤词；text 为空表示清空"""
        try:
            inp.clear()
            if text:
                inp.send_keys(text)
            time.sleep(0.3)
            return True
        except Exception:
            return False

    def _wait_items(self, budget: float = 1.2) -> list:
        """
        等待选项列表稳定：远程搜索要等接口回来。
        连续两次采样数量一致且非空即视为稳定；超时返回最后一次快照。
        """
        driver = self.driver
        end = time.time() + budget
        last, stable, items = [], 0, []
        while time.time() < end:
            items = [
                i
                for i in driver.find_elements(By.CSS_SELECTOR, DROPDOWN_ITEM)
                if i.is_displayed()
            ]
            if items and len(items) == len(last):
                stable += 1
                if stable >= 2:
                    return items
            else:
                stable = 0
            last = items
            time.sleep(0.12)
        return [
            i
            for i in driver.find_elements(By.CSS_SELECTOR, DROPDOWN_ITEM)
            if i.is_displayed()
        ]

    def _dismiss_open_dropdown(self) -> None:
        """只有真的存在可见下拉面板时才发 ESC，避免在输入框里误触 blur"""
        if not self._dropdown_panel_visible():
            return
        try:
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            time.sleep(0.15)
        except Exception:
            pass

    def close_poppers(self) -> None:
        """兼容旧名"""
        self._dismiss_open_dropdown()

    def _click_el(self, el) -> None:
        """真实点击优先；stale 必须抛给上层重试，不能退化成 JS 点击"""
        try:
            el.click()
        except StaleElementReferenceException:
            raise
        except Exception:
            self.driver.execute_script("arguments[0].click();", el)

    @staticmethod
    def _match_item(items, option_text: str):
        """精确 → 忽略大小写 → 包含 → 双向包含"""
        target = next((i for i in items if (i.text or "").strip() == option_text), None)
        if target is not None:
            return target
        low = option_text.strip().lower()
        target = next((i for i in items if (i.text or "").strip().lower() == low), None)
        if target is not None:
            return target
        target = next((i for i in items if option_text in (i.text or "")), None)
        if target is not None:
            return target
        return next(
            ((i for i in items if (i.text or "").strip() and (i.text or "").strip() in option_text)),
            None,
        )

    @staticmethod
    def option_candidates(option_text: str) -> list:
        """英文枚举 → 前端中文文案候选：原值优先，再按 OPTION_ALIASES 逐个尝试"""
        raw = (option_text or "").strip()
        cands = [raw] if raw else []
        for alias in OPTION_ALIASES.get(raw.upper(), []):
            if alias not in cands:
                cands.append(alias)
        return cands

    def select_real(
        self,
        select_el,
        option_text: str,
        timeout: int = 10,
        confirm: bool = True,
        candidates=None,
        search_keys=None,
    ):
        """
        打开面板 →（按搜索词过滤）→ 点中选项 → 断言已选中。

        支持三种下拉：
        1. 静态下拉（优先级 / 严重程度）：直接匹配候选文案；
        2. 本地过滤下拉：输入 option_text 过滤后再匹配；
        3. 远程搜索下拉（指派给）：必须输入关键字才出数据，
           把可能的搜索词放进 search_keys，逐个尝试并等接口返回。

        option_text 写英文枚举（MEDIUM / SERIOUS）时自动映射成中文文案。
        """
        driver = self.driver
        tried = candidates or self.option_candidates(option_text)
        keys = [k for k in (search_keys or []) if k]

        self._dismiss_open_dropdown()
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", select_el)

        wrappers = select_el.find_elements(By.CSS_SELECTOR, ".el-select__wrapper")
        trigger = wrappers[0] if wrappers else select_el
        self._click_el(trigger)

        # 远程搜索初始可能是 0 条，所以等「面板出现」而不是「有选项」
        WebDriverWait(driver, timeout).until(lambda d: self._dropdown_panel_visible())

        inp = self._select_input(select_el)

        def match(items):
            for cand in tried:
                t = self._match_item(items, cand)
                if t is not None:
                    return t, cand
            return None, option_text

        target, used = None, option_text

        # ---- 1) 指定了搜索词：逐个输入，等远程结果回来再匹配 ----
        if keys and inp is not None:
            for key in keys:
                if not self._type_filter(inp, key):
                    continue
                items = self._wait_items(1.2)
                target, used = match(items)
                if target is not None:
                    print(f"[BUG-SELECT] 搜索词 {key!r} 命中 «{used}»")
                    break
                print(f"[BUG-SELECT] 搜索词 {key!r} 无命中（当前 {len(items)} 项）")
            if target is None:  # 全部搜索词失败：清空看全量
                print("[BUG-SELECT] 搜索词全部未命中，清空输入查看全量列表")
                self._type_filter(inp, "")
                target, used = match(self._wait_items(1.0))
        # ---- 2) 没给搜索词：先看当前列表，空则用 option_text 试一次 ----
        else:
            target, used = match(self._wait_items(0.8))
            if target is None and inp is not None:
                self._type_filter(inp, option_text)
                target, used = match(self._wait_items(1.2))
                if target is None:
                    self._type_filter(inp, "")
                    target, used = match(self._wait_items(1.0))

        if target is None:
            items = [
                i
                for i in driver.find_elements(By.CSS_SELECTOR, DROPDOWN_ITEM)
                if i.is_displayed()
            ]
            empty = self._dropdown_empty_text()
            raise AssertionError(
                f"下拉中没有 «{option_text}»（候选 {tried}，搜索词 {keys}）；"
                f"可见选项 {len(items)} 项：{[(i.text or '').strip() for i in items][:10]}；"
                f"下拉空状态提示：{empty or '无'}"
            )

        # ---- 点选：列表可能因过滤重渲染，允许重查 ----
        for attempt in range(3):
            try:
                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", target
                )
                self._click_el(target)
                break
            except StaleElementReferenceException:
                print(f"[BUG-SELECT] 选项第 {attempt + 1} 次 stale，重查列表")
                items = [
                    i
                    for i in driver.find_elements(By.CSS_SELECTOR, DROPDOWN_ITEM)
                    if i.is_displayed()
                ]
                target, used = match(items)
                if target is None:
                    raise AssertionError(f"重查后仍找不到 «{option_text}»")
                time.sleep(0.2)
        else:
            raise AssertionError(f"点击选项 «{option_text}» 连续 stale 失败")

        if confirm:
            try:
                WebDriverWait(driver, 5).until(lambda d: used in (select_el.text or ""))
            except StaleElementReferenceException:
                raise
            except TimeoutException:
                print(f"[BUG-SELECT] ⚠️ 未确认已选中 «{used}»，下拉框当前文本：{select_el.text!r}")
                raise
        if used != option_text:
            print(f"[BUG-SELECT] ✅ 已选中 «{used}»（由 {option_text} 映射）")
        else:
            print(f"[BUG-SELECT] ✅ 已选中 «{used}»")

    def select_field(
        self,
        title_keyword: str,
        *keywords,
        option: str,
        index=None,
        retries: int = 3,
        timeout: int = 10,
        search_keys=None,
    ):
        """
        按字段名选值。每次尝试都重新取 dialog 和字段元素，
        遇到 stale 自动重试，不让异常冒到用例层。

        search_keys 用于远程搜索类下拉（指派给）：逐个输入等待接口返回。
        """
        last_err = None
        for attempt in range(1, retries + 1):
            dialog = self.visible_dialog(title_keyword=title_keyword)
            field = self.find_field(dialog, ("select",), *keywords, index=index)
            try:
                self.select_real(
                    field["el"],
                    option,
                    timeout=timeout,
                    search_keys=search_keys,
                )
                return True
            except StaleElementReferenceException as err:
                last_err = err
                print(
                    f"[BUG-SELECT] ⚠️ 第 {attempt}/{retries} 次 stale"
                    f"（字段 {keywords}），重查元素后重试"
                )
                time.sleep(0.3)
        raise AssertionError(
            f"字段 {keywords} 选值 «{option}» 连续 {retries} 次 stale 失败：{last_err}"
        )

    @staticmethod
    def person_search_keys(name: str) -> list:
        """
        从显示名派生远程搜索词：整串 → 英文片段 → 中文片段。
        「DEV测试」→ ['DEV测试', 'DEV', '测试']
        前端按 username 搜索时，可用 assignee_search_keys 显式传入（如 ('dev01',)）
        """
        raw = (name or "").strip()
        if not raw:
            return []
        keys = [raw]
        for seg in re.findall(r"[A-Za-z0-9_.\-]+", raw):
            if seg != raw and seg not in keys:
                keys.append(seg)
        for seg in re.split(r"[A-Za-z0-9_.\-]+", raw):
            seg = seg.strip()
            if seg and seg != raw and seg not in keys:
                keys.append(seg)
        return keys

    # 兼容旧方法名
    def safe_set_el_select(self, select_locator, option_text: str):
        el = self.visible(select_locator)
        self.select_real(el, option_text)

    def safe_set_el_select_by_index(self, index: int, option_text: str):
        dialog = self.visible_dialog()
        el = self.find_field(dialog, ("select",), index=index)["el"]
        self.select_real(el, option_text)

    # ===================================================================
    # 3. 输入框 / 文本域（每次重查 + 真输入）
    # ===================================================================
    def dialog_text_inputs(self, dialog) -> list:
        """兼容旧名：返回弹窗内非下拉输入框"""
        return [f["el"] for f in self.form_fields(dialog) if f["kind"] == "input"]

    def dialog_textareas(self, dialog) -> list:
        return [f["el"] for f in self.form_fields(dialog) if f["kind"] == "textarea"]

    def set_text(self, el, value: str) -> None:
        """clear + send_keys，比 JS 赋值更能驱动 v-model"""
        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        el.click()
        el.clear()
        el.send_keys(value)

    def set_field_text(
        self,
        title_keyword: str,
        *keywords,
        value: str,
        kind: str = "input",
        index=None,
        retries: int = 2,
    ):
        """按字段名填文本。每次尝试都重新取 dialog 和字段元素。"""
        last_err = None
        for attempt in range(1, retries + 1):
            dialog = self.visible_dialog(title_keyword=title_keyword)
            field = self.find_field(dialog, (kind,), *keywords, index=index)
            try:
                self.set_text(field["el"], value)
                return True
            except StaleElementReferenceException as err:
                last_err = err
                print(
                    f"[BUG-FIELD] ⚠️ 第 {attempt}/{retries} 次 stale"
                    f"（字段 {keywords}），重查后重试"
                )
                time.sleep(0.3)
        raise AssertionError(f"字段 {keywords} 输入连续 stale 失败：{last_err}")

    # ===================================================================
    # 4. 页面动作：打开 / 搜索
    # ===================================================================
    def open(self, project_id: int | None = None) -> None:
        path = f"/projects/{project_id}/bugs" if project_id else "/bugs"
        self.open_path(path)
        print(f"[DEBUG-BUG-PAGE] 目标path={path}, 当前url={self.driver.current_url}")
        WebDriverWait(self.driver, 20).until(EC.url_contains(path))
        print("[DEBUG-BUG-PAGE] ✅ URL 跳转成功")

        self.visible(self.SEARCH_TOOLBAR, timeout=20)
        print("[DEBUG-BUG-PAGE] ✅ 搜索工具栏 .search-toolbar 已出现")
        try:
            self.visible(self.SEARCH_FORM, timeout=12)
            print("[DEBUG-BUG-PAGE] ✅ .search-form 渲染完成")
        except Exception:
            print("[DEBUG-BUG-PAGE] ⚠️ search-form 超时，继续（接口加载慢）")
        print("[DEBUG-BUG-PAGE] open() 页面基础容器就绪，结束")

    def search_select(self, *keywords, value: str, fallback_label: str = "") -> bool:
        """搜索区下拉：字段名定位失败时退回旧 XPath"""
        for attempt in range(2):
            form = self.visible(self.SEARCH_FORM, timeout=10)
            field = self.find_field(form, ("select",), *keywords, strict=False)
            if field is None:
                if not fallback_label:
                    return False
                el = self.visible(
                    (By.XPATH, self.SEARCH_SELECT[1].replace("{label}", fallback_label))
                )
            else:
                el = field["el"]
            try:
                self.select_real(el, value)
                return True
            except StaleElementReferenceException:
                print(f"[BUG-SEARCH] 第 {attempt + 1} 次 stale，重查搜索表单")
                time.sleep(0.2)
        return False

    def wait_list_idle(self, timeout: float = 10.0) -> bool:
        """等表格 loading 遮罩消失（提交 / 搜索后列表重新加载时用）"""
        driver = self.driver
        end = time.time() + timeout
        while time.time() < end:
            masks = [
                m
                for m in driver.find_elements(By.CSS_SELECTOR, ".el-loading-mask")
                if m.is_displayed()
            ]
            if not masks:
                return True
            time.sleep(0.25)
        print("[BUG-LIST] ⚠️ 列表 loading 遮罩未消失，继续")
        return False

    def click_search(self, timeout: int = 15):
        """点搜索按钮：文字定位优先，失败退回 class 定位"""
        try:
            btn = self.clickable(self.BTN_SEARCH, timeout=timeout)
        except Exception:
            print("[BUG-SEARCH] ⚠️ 文字定位未命中，退回 .el-button--primary")
            btn = self.clickable(self.BTN_SEARCH_FALLBACK, timeout=timeout)
        print(
            f"[BUG-SEARCH] 按钮 displayed={btn.is_displayed()} enabled={btn.is_enabled()} "
            f"text={btn.text.strip()!r}"
        )
        self._click_el(btn)
        return btn

    def search(self, title: str = "", status: str = "", severity: str = "", assignee: str = ""):
        self.wait_list_idle(timeout=3)

        if title:
            el = self.visible(self.INPUT_TITLE, timeout=10)
            el.clear()
            el.send_keys(title)

        if status:
            self.search_select(*KW_STATUS, value=status, fallback_label="状态")
        if severity:
            self.search_select(*KW_SEVERITY, value=severity, fallback_label="严重程度")
        if assignee:
            self.search_select(*KW_ASSIGNEE, value=assignee, fallback_label="指派人")

        self._dismiss_open_dropdown()
        self.click_search(timeout=15)
        self.wait_list_idle(timeout=10)
        time.sleep(0.3)

    def get_empty_text(self) -> str:
        return self.visible(self.EMPTY_TEXT).text.strip()

    def is_row_updated(self, title: str) -> bool:
        loc = (self.ROW_UPDATED_CLASS[0], self.ROW_UPDATED_CLASS[1].replace("{title}", title))
        try:
            self.visible(loc, timeout=2)
            return True
        except Exception:
            return False

    def click_row_action(self, title: str, btn_text: str):
        loc = (
            self.ROW_ACTION_BTN[0],
            self.ROW_ACTION_BTN[1]
            .replace("{title}", title)
            .replace("{btn_text}", btn_text),
        )
        self.click(loc)

    # ===================================================================
    # 5. 新建缺陷弹窗
    # ===================================================================
    def wait_create_btn_ready(self):
        print("[DEBUG-BUG-PAGE] 等待【提交缺陷】按钮")
        btn = self.clickable(self.BTN_CREATE, timeout=20)
        print("[DEBUG-BUG-PAGE] ✅ 提交缺陷按钮已可点击")
        return btn

    def open_create_dialog(self):
        self.wait_create_btn_ready()
        self.click(self.BTN_CREATE)
        dialog = self.visible_dialog(title_keyword="提交缺陷")
        print(f"[BUG-DIALOG] 创建弹窗已打开，标题：{self._title_of(dialog)!r}")
        print(
            f"[BUG-DIALOG] 字段清单："
            f"{[(f['kind'], f['label']) for f in self.form_fields(dialog)]}"
        )
        print(
            f"[BUG-DIALOG] 字段当前值："
            f"{[(f['label'], self._field_value(f)) for f in self.form_fields(dialog)]}"
        )
        return dialog

    def _field_value(self, field) -> str:
        """读字段当前显示值，用于诊断「所属项目未选导致指派给为空」这类问题"""
        try:
            if field["kind"] == "select":
                return (field["el"].text or "").strip()
            return (field["el"].get_attribute("value") or "").strip()
        except Exception:
            return "<读取失败>"

    def fill_create_form(
        self,
        title: str,
        assignee: str,
        module: str = "",
        found_version: str = "",
        env: str = "",
        priority: str = "MEDIUM",
        severity: str = "SERIOUS",
        description: str = "",
        expect: str = "",
        actual: str = "",
        assignee_search_keys=None,
    ):
        """
        按字段名填写新建缺陷表单（不缓存元素，每次重查）。

        assignee 走远程搜索下拉：默认从显示名派生搜索词
        （「DEV测试」→ DEV测试 / DEV / 测试）；
        若前端按 username 搜索，传 assignee_search_keys=("dev01",) 即可。
        """
        dialog = self.visible_dialog(title_keyword="提交缺陷")

        # ---- 文本字段 ----
        for kw, val, name, idx in (
            (KW_TITLE, title, "缺陷标题", 0),
            (KW_MODULE, module, "所属模块", 1),
            (KW_VERSION, found_version, "发现版本", 2),
            (KW_ENV, env, "环境", 3),
        ):
            if not val:
                continue
            print(f"[BUG-FORM] {name} ← {val}")
            self.set_field_text("提交缺陷", *kw, value=val, index=idx)

        # ---- 下拉字段 ----
        if priority:
            self.select_field("提交缺陷", *KW_PRIORITY, option=priority)
        if severity:
            self.select_field("提交缺陷", *KW_SEVERITY, option=severity)
        if assignee:
            keys = assignee_search_keys or self.person_search_keys(assignee)
            print(f"[BUG-FORM] 指派给 ← {assignee}，远程搜索词 {keys}")
            self.select_field(
                "提交缺陷", *KW_ASSIGNEE, option=assignee, search_keys=keys
            )

        # ---- 长文本 ----
        for kw, val, name, idx in (
            (KW_DESC, description, "复现步骤", 0),
            (KW_EXPECT, expect, "预期结果", 1),
            (KW_ACTUAL, actual, "实际结果", 2),
        ):
            if not val:
                continue
            print(f"[BUG-FORM] {name} ← {val}")
            self.set_field_text(
                "提交缺陷", *kw, value=val, kind="textarea", index=idx
            )

        self._dismiss_open_dropdown()
        print("[BUG-FORM] ✅ 表单填写完成")
        return dialog

    def click_ai_optimize(self, timeout: int = 30):
        btn = self.clickable(self.BTN_AI_OPTIMIZE, timeout=15)
        self._click_el(btn)
        end = time.time() + timeout
        while time.time() < end:
            try:
                if "is-loading" not in (btn.get_attribute("class") or ""):
                    print("[BUG-AI] ✅ 润色 loading 已结束")
                    return
            except StaleElementReferenceException:
                return
            time.sleep(0.3)
        print("[BUG-AI] ⚠️ 等待 loading 结束超时，继续")

    def upload_attachment(self, file_path: str):
        abs_path = os.path.abspath(file_path)
        if not os.path.isfile(abs_path):
            raise FileNotFoundError(f"附件不存在：{abs_path}")
        el = self.driver.find_element(*self.UPLOAD_FILE_INPUT)
        el.send_keys(abs_path)
        print(f"[BUG-UPLOAD] ✅ 已选择文件：{abs_path}")

    def submit_create(self, timeout: int = 15):
        dialog = self.visible_dialog(title_keyword="提交缺陷")
        self._dismiss_open_dropdown()

        errs = [
            e.text
            for e in dialog.find_elements(By.CSS_SELECTOR, ".el-form-item__error")
            if e.is_displayed()
        ]
        if errs:
            raise AssertionError(f"提交前仍存在校验错误，说明有字段没填上：{errs}")

        dialog.find_element(*self.BTN_DIALOG_SUBMIT).click()
        print("[BUG-SUBMIT] 已点击确定")

        self.wait_dialogs_closed(timeout=timeout, msg="提交后新建缺陷弹窗未关闭")
        self.wait_list_idle(timeout=10)  # 等列表刷新完再让用例搜索
        print("[BUG-SUBMIT] ✅ 弹窗已关闭，提交完成")

    def cancel_create(self, timeout: int = 10):
        dialog = self.visible_dialog(title_keyword="提交缺陷")
        dialog.find_element(*self.BTN_DIALOG_CANCEL).click()
        self.wait_dialogs_closed(timeout=timeout, msg="取消后弹窗未关闭")

    # ===================================================================
    # 6. 指派缺陷弹窗
    # ===================================================================
    def open_assign_dialog(self, title: str):
        self.click_row_action(title, "指派")
        dialog = self.visible_dialog(title_keyword="指派缺陷")
        print(
            f"[BUG-ASSIGN] 指派弹窗已打开，字段清单："
            f"{[(f['kind'], f['label']) for f in self.form_fields(dialog)]}"
        )
        return dialog

    def assign_to(self, assignee_name: str, dialog=None, timeout: int = 15):
        # dialog 参数保留兼容旧调用；实际每次都重新取可见弹窗
        self.select_field("指派缺陷", *KW_ASSIGNEE, option=assignee_name, index=0)
        self._dismiss_open_dropdown()

        dialog = self.visible_dialog(title_keyword="指派缺陷")
        dialog.find_element(*self.BTN_DIALOG_SUBMIT).click()
        self.wait_dialogs_closed(timeout=timeout, msg="指派弹窗未关闭，指派可能失败")
        print(f"[BUG-ASSIGN] ✅ 已指派给 {assignee_name}")

    # ===================================================================
    # 7. 项目导航：项目栏 → 项目 → 缺陷 tab → 详情弹窗 → 接受缺陷
    # ===================================================================
    NAV_PROJECT_TEXTS = ("项目", "项目中心", "我的项目", "项目列表")
    BUG_ENTRY_TEXTS = ("缺陷", "缺陷管理", "Bug", "Bugs")
    DETAIL_BUTTON_TEXTS = ("详情", "查看", "查看详情")
    ACCEPT_BUTTON_TEXTS = ("接受", "接收", "领取", "认领", "接受缺陷", "接收缺陷")

    def find_text_elements(self, text: str, exact: bool = True, timeout: float = 10) -> list:
        """按可见文本找元素（精确 > 包含），返回文档顺序的可见元素列表"""
        driver = self.driver
        safe = (text or "").replace("'", "")
        if exact:
            xpath = f"//*[normalize-space()='{safe}']"
        else:
            xpath = f"//*[contains(normalize-space(), '{safe}')]"
        end = time.time() + timeout
        while True:
            found = []
            for el in driver.find_elements(By.XPATH, xpath):
                try:
                    if el.is_displayed():
                        found.append(el)
                except StaleElementReferenceException:
                    continue
            if found or time.time() > end:
                return found
            time.sleep(0.25)

    def click_by_text(self, text: str, exact: bool = True, timeout: float = 10):
        """点最内层的文本节点（点击会冒泡到卡片 / 菜单项）"""
        els = self.find_text_elements(text, exact=exact, timeout=timeout)
        if not els:
            return None
        self._click_el(els[-1])
        return els[-1]

    def open_project_center(self, timeout: int = 15) -> bool:
        """点导航「项目」进项目中心；点不到则直接访问 /projects"""
        for text in self.NAV_PROJECT_TEXTS:
            el = self.click_by_text(text, timeout=3)
            if el is not None:
                print(f"[BUG-PROJECT] 点击导航「{text}」")
                break
        else:
            print("[BUG-PROJECT] ⚠️ 未点到「项目」导航，直接访问 /projects")
            self.open_path("/projects")

        self.wait_list_idle(10)
        WebDriverWait(self.driver, timeout).until(EC.url_contains("/projects"))
        print(f"[BUG-PROJECT] 已进入项目中心：{self.driver.current_url}")
        return True

    def open_project(self, project_name: str = "", project_id: int | None = None, timeout: int = 15) -> bool:
        """
        从项目栏进入指定项目，返回是否真的走了 UI 路径：
        1) project_name 有值 → 项目中心点卡片，返回 True；
        2) 只有 project_id → 直接开 /projects/{id}/bugs，返回 False。
        """
        if project_name:
            self.open_project_center(timeout=timeout)
            card = self.click_by_text(project_name, exact=False, timeout=timeout)
            if card is not None:
                print(f"[BUG-PROJECT] 点击项目卡片「{project_name}」")
                self.wait_list_idle(10)
                time.sleep(0.3)
                return True
            print(f"[BUG-PROJECT] ⚠️ 未找到项目卡片「{project_name}」，改用 project_id 直达")

        if project_id is not None:
            self.open(project_id)
            return False
        raise AssertionError("既没有匹配到项目卡片，也没有传 project_id")

    def open_bug_entry(self, timeout: int = 15) -> bool:
        """项目页里点「缺陷」入口，并等缺陷列表容器出现"""
        for text in self.BUG_ENTRY_TEXTS:
            el = self.click_by_text(text, exact=True, timeout=4)
            if el is not None:
                print(f"[BUG-PROJECT] 点击「{text}」入口")
                self.wait_list_idle(10)
                self.visible(self.SEARCH_TOOLBAR, timeout=timeout)
                return True
        raise AssertionError(
            f"项目页没有找到缺陷入口 {self.BUG_ENTRY_TEXTS}；"
            f"当前 URL：{self.driver.current_url}"
        )

    def detail_panel(self, timeout: float = 15):
        """返回当前可见的详情弹窗 / 抽屉；都没有则返回 None"""
        end = time.time() + timeout
        while time.time() < end:
            for css in (".el-drawer", ".el-dialog"):
                for el in self.driver.find_elements(By.CSS_SELECTOR, css):
                    try:
                        if el.is_displayed():
                            return el
                    except StaleElementReferenceException:
                        continue
            time.sleep(0.2)
        return None

    def open_bug_detail(self, title: str, timeout: int = 15):
        """列表行点「详情」，等详情弹窗 / 抽屉渲染完成"""
        self.click_row_action(title, "详情")
        panel = self.detail_panel(timeout=timeout)
        if panel is None:
            print("[BUG-DETAIL] ⚠️ 未检测到详情弹窗/抽屉，可能跳转到了独立页面")
            return None
        print(f"[BUG-DETAIL] 详情弹窗已打开，标题：{self._title_of(panel)!r}")
        return panel

    def click_button_in(self, scope, *texts, timeout: float = 10):
        """在指定容器内按文字点按钮"""
        end = time.time() + timeout
        while True:
            for text in texts:
                xpath = f".//button[contains(normalize-space(), '{text}')]"
                for btn in scope.find_elements(By.XPATH, xpath):
                    try:
                        if btn.is_displayed() and btn.is_enabled():
                            return btn
                    except StaleElementReferenceException:
                        continue
            if time.time() > end:
                return None
            time.sleep(0.2)

    def _confirm_message_box(self):
        """Element Plus 的 MessageBox 二次确认"""
        for box in self.driver.find_elements(By.CSS_SELECTOR, ".el-message-box"):
            try:
                if not box.is_displayed():
                    continue
                for btn in box.find_elements(By.TAG_NAME, "button"):
                    if btn.is_displayed() and any(
                        k in (btn.text or "") for k in ("确定", "确认", "是", "OK")
                    ):
                        return btn
            except StaleElementReferenceException:
                continue
        return None

    def accept_bug(self, timeout: int = 15) -> str:
        """
        在详情弹窗里「接受缺陷」：点接受 → 处理可能的二次确认 → 等列表刷新。
        返回实际点到的按钮文案。
        """
        panel = self.detail_panel(timeout=6)
        scope = panel if panel is not None else self.driver

        btn = self.click_button_in(scope, *self.ACCEPT_BUTTON_TEXTS, timeout=timeout)
        if btn is None:
            visible_buttons = []
            try:
                visible_buttons = [
                    (b.text or "").strip()
                    for b in scope.find_elements(By.TAG_NAME, "button")
                    if b.is_displayed()
                ]
            except Exception:
                pass
            raise AssertionError(
                f"详情弹窗内没有接受按钮 {self.ACCEPT_BUTTON_TEXTS}；"
                f"现有按钮：{visible_buttons}"
            )

        label = (btn.text or "").strip()
        print(f"[BUG-DETAIL] 点击「{label}」")
        self._click_el(btn)

        box = self._confirm_message_box()
        if box is not None:
            print(f"[BUG-DETAIL] 二次确认「{(box.text or '').strip()}」")
            self._click_el(box)

        self.wait_list_idle(10)
        print(f"[BUG-DETAIL] ✅ 已{label}缺陷")
        return label

    def close_detail(self, timeout: int = 10) -> bool:
        """关闭详情弹窗 / 抽屉，避免遮罩挡住后续登出、切换账号"""
        panel = self.detail_panel(timeout=3)
        if panel is None:
            return False

        for css in (".el-drawer__close-btn", ".el-dialog__headerbtn", ".el-drawer__headerbtn"):
            for btn in panel.find_elements(By.CSS_SELECTOR, css):
                try:
                    if btn.is_displayed():
                        self._click_el(btn)
                        print("[BUG-DETAIL] 已点击关闭按钮")
                        break
                except StaleElementReferenceException:
                    continue
            else:
                continue
            break
        else:
            self._dismiss_open_dropdown()
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            print("[BUG-DETAIL] 未找到关闭按钮，改用 ESC")

        end = time.time() + timeout
        while time.time() < end:
            if self.detail_panel(timeout=0.5) is None:
                print("[BUG-DETAIL] ✅ 详情弹窗已关闭")
                return True
            time.sleep(0.25)
        print("[BUG-DETAIL] ⚠️ 详情弹窗未确认关闭")
        return False
