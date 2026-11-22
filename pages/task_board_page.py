"""任务看板 POM。

源码是 src/views/task/TaskBoard.vue。
包含了极高的状态流转、复杂的筛选、抽屉面板及多个操作弹窗。

【本版修正】
1. TASK_ROW_STATUS 的 XPath 谓词错位：原来 `normalize-space(.)='{title}'` 挂在 tr 上，
   tr 的 string-value 是整行文本拼接，永远不等于标题 → 一条都匹配不到。
   已把谓词挪到 span 里。
2. get_task_status 的 td[2] 写死：改成按表头「状态」找列号，后面前端插列也不会错位。
3. get_drawer_hint：`.drawer-footer__hint` 是 `v-if="drawerHint"`，有可执行动作时
   drawerHint 为空、整个 span 不渲染 → 原来会硬等 10 秒超时。现在无提示返回空串。
4. 新增 close_drawer()：接受任务后抽屉仍开着，要断言列表状态得先关抽屉。
5. 下拉选项改为「先精确、再包含」：容忍全角括号 / 空格差异。
"""
from __future__ import annotations

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from pages.base_page import BasePage
from utils.waits import (
    wait_for_element_visible,
    wait_for_element_clickable,
    wait_for_element_invisible,
    wait_for_first_displayed,
)


class TaskBoardPage(BasePage):
    # ================= 1. 顶部与筛选区 =================
    HEADER_NAME = (By.CSS_SELECTOR, ".board-header__name")
    READONLY_TIP = (By.CSS_SELECTOR, ".board-readonly-tip")

    FILTER_INPUT_KEYWORD = (By.CSS_SELECTOR, ".filter-bar input[placeholder='请输入标题关键字']")
    FILTER_SELECT_STATUS = (By.XPATH, "//div[contains(@class,'filter-bar')]//div[contains(@class,'el-select')][1]")
    FILTER_SELECT_ASSIGNEE = (By.XPATH, "//div[contains(@class,'filter-bar')]//div[contains(@class,'el-select')][2]")
    OPTION_DROPDOWN = (By.XPATH, "//li[contains(@class,'el-select-dropdown__item')]//span[text()='{text}']")

    BTN_SEARCH = (By.XPATH, "//div[contains(@class,'filter-bar')]//button[contains(., '查询')]")
    BTN_RESET = (By.XPATH, "//div[contains(@class,'filter-bar')]//button[contains(., '重置')]")
    BTN_CREATE = (By.XPATH, "//div[contains(@class,'filter-bar')]//button[contains(., '新建任务')]")
    BTN_REFRESH = (By.XPATH, "//div[contains(@class,'filter-bar')]//button[contains(., '刷新')]")

    # ================= 2. 表格区域 =================
    TABLE_HEADER_TH = (By.CSS_SELECTOR, ".el-table__header th")
    TASK_ROW_TITLE = (By.XPATH, "//span[contains(@class,'task-title-link') and normalize-space(.)='{title}']")
    TASK_ROW_ACTION = (By.XPATH, "//tr[.//span[contains(@class,'task-title-link') and normalize-space(.)='{title}']]//button[contains(., '{btn_text}')]")
    # 状态列：列号由 get_task_status 按表头动态算，模板里 td[2] 只作兜底
    TASK_ROW_STATUS = (By.XPATH, "//tr[.//span[contains(@class,'task-title-link') and normalize-space(.)='{title}']]/td[{index}]//span[contains(@class,'el-tag')]")

    # ================= 3. 新建任务弹窗 =================
    CREATE_DIALOG_TITLE = (By.XPATH, "//div[contains(@class,'el-dialog')]//span[contains(@class,'el-dialog__title') and contains(., '新建任务')]")
    DIALOG_INPUT = (By.XPATH, "//div[contains(@class,'el-dialog')]//label[contains(., '{label}')]/following-sibling::div//input")
    DIALOG_TEXTAREA = (By.XPATH, "//div[contains(@class,'el-dialog')]//label[contains(., '{label}')]/following-sibling::div//textarea")
    DIALOG_SELECT = (By.XPATH, "//div[contains(@class,'el-dialog')]//label[contains(., '{label}')]/following-sibling::div//div[contains(@class,'el-select')]")
    DIALOG_FILE_UPLOAD = (By.CSS_SELECTOR, ".el-dialog input[type='file']")
    DIALOG_BTN_SUBMIT = (By.XPATH, "//div[contains(@class,'el-dialog__footer')]//button[contains(., '确定')]")
    DIALOG_BTN_CANCEL = (By.XPATH, "//div[contains(@class,'el-dialog__footer')]//button[contains(., '取消')]")

    # 日期选择弹窗popper
    DATETIME_POPPER = (By.CSS_SELECTOR, ".el-date-picker__popper")

    # ================= 4. 任务详情抽屉 (Drawer) =================
    DRAWER_TITLE = (By.CSS_SELECTOR, ".task-detail__title")
    DRAWER_HINT = (By.CSS_SELECTOR, ".drawer-footer__hint")
    DRAWER_CLOSE_BTN = (By.CSS_SELECTOR, ".el-drawer__close-btn")
    # 抽屉底部操作按钮
    DRAWER_BTN = (By.XPATH, "//div[contains(@class,'drawer-footer__actions')]//button[contains(., '{btn_text}')]")
    DRAWER_BLOCK_CARD = (By.CSS_SELECTOR, ".block-card")

    # ================= 5. 全局确认框 (MessageBox) =================
    MSG_BOX = (By.CSS_SELECTOR, ".el-message-box")
    MSG_BOX_CONFIRM = (By.CSS_SELECTOR, ".el-message-box__btns .el-button--primary")

    # ================= 6. 全局 el-message 提示 =================
    EL_MESSAGE = (By.CSS_SELECTOR, ".el-message")
    EL_MESSAGE_TEXT = (By.XPATH, "//div[contains(@class,'el-message')]//p[normalize-space()='{msg}']")
    EL_MESSAGE_TEXT_CONTAINS = (By.XPATH, "//div[contains(@class,'el-message')]//p[contains(normalize-space(.),'{msg}')]")

    # ================= 7. 各种操作弹窗 =================
    ACTION_DIALOG_TEXTAREA = (By.XPATH, "//div[contains(@class,'el-dialog')]//label[contains(., '{label}')]/following-sibling::div//textarea")
    ACTION_DIALOG_SUBMIT = (By.XPATH, "//div[contains(@class,'el-dialog__footer')]//button[contains(., '{btn_text}')]")

    # ================= 页面初始化 =================
    def open(self, project_id: int) -> None:
        """通过项目 ID 打开看板"""
        self.open_path(f"/projects/{project_id}/board")
        self.visible(self.HEADER_NAME)

    def is_readonly(self) -> bool:
        """判断项目是否已关闭（只读）"""
        try:
            return self.visible(self.READONLY_TIP, timeout=2).is_displayed()
        except Exception:
            return False

    # ================= 内部工具 =================
    def _column_index(self, header_text: str, default: int = 2) -> int:
        """按表头文字找列号（1 起）。表头还没渲染出来时用 default。"""
        try:
            for i, th in enumerate(self.driver.find_elements(*self.TABLE_HEADER_TH), start=1):
                if header_text in (th.text or ""):
                    return i
        except Exception:
            pass
        return default

    def _pick_option(self, text: str, timeout: float = 10):
        """选下拉项：先精确匹配，失败再退化成包含匹配（容忍全角括号/空格）。"""
        exact = (By.XPATH,
                 f"//li[contains(@class,'el-select-dropdown__item')]//span[normalize-space(text())='{text}']")
        try:
            return wait_for_first_displayed(self.driver, exact, timeout=3)
        except Exception:
            loose = (By.XPATH,
                     f"//li[contains(@class,'el-select-dropdown__item')][.//span[contains(normalize-space(.),'{text}')]]")
            return wait_for_first_displayed(self.driver, loose, timeout)

    # ================= 筛选操作 =================
    def search(self, keyword: str = "", status: str = "", assignee: str = ""):
        if keyword:
            self.type_text(self.FILTER_INPUT_KEYWORD, keyword)
        if status:
            self.click(self.FILTER_SELECT_STATUS)
            self._pick_option(status).click()
            wait_for_element_invisible(self.driver, (By.CSS_SELECTOR, ".el-select-dropdown"))
        if assignee:
            self.click(self.FILTER_SELECT_ASSIGNEE)
            self._pick_option(assignee).click()
            wait_for_element_invisible(self.driver, (By.CSS_SELECTOR, ".el-select-dropdown"))
        self.click(self.BTN_SEARCH)

    def reset(self):
        self.click(self.BTN_RESET)

    def refresh(self):
        self.click(self.BTN_REFRESH)

    # ================= 表格与行内操作 =================
    def get_task_status(self, title: str, timeout: float = 10) -> str:
        """获取列表中指定任务的当前状态（列号按表头「状态」动态算）"""
        idx = self._column_index("状态", 2)
        loc = (self.TASK_ROW_STATUS[0], self.TASK_ROW_STATUS[1]
               .replace("{title}", title).replace("{index}", str(idx)))
        return self.visible(loc, timeout=timeout).text.strip()

    def get_row_title(self, title: str, timeout: float = 10) -> str:
        """等任务行出现并返回标题文本（wait_row 返回元素，这里只取文本）。"""
        loc = (self.TASK_ROW_TITLE[0], self.TASK_ROW_TITLE[1].replace("{title}", title))
        el = wait_for_element_visible(self.driver, loc, timeout)
        return (getattr(el, "text", "") or "").strip()

    def wait_task_status(self, title: str, expect: str, timeout: float = 15) -> str:
        """轮询等列表状态变成 expect（抽屉操作后列表是异步刷新的）。

        超时返回最后读到的值，交给用例 assert，报错信息里能带出实际状态。
        """
        def _probe(_driver):
            try:
                return self.get_task_status(title, timeout=1)
            except Exception:
                return False

        try:
            WebDriverWait(self.driver, timeout, poll_frequency=0.5).until(
                lambda d: _probe(d) == expect
            )
        except Exception:
            pass
        try:
            return self.get_task_status(title, timeout=2)
        except Exception:
            return "<取不到状态>"

    def click_task_title(self, title: str):
        """点击表格中的任务标题，打开抽屉"""
        loc = (self.TASK_ROW_TITLE[0], self.TASK_ROW_TITLE[1].replace("{title}", title))
        self.click(loc)
        self.visible(self.DRAWER_TITLE)

    def click_row_action(self, title: str, btn_text: str):
        """点击表格某行的操作按钮（如：详情、删除）"""
        loc = (self.TASK_ROW_ACTION[0], self.TASK_ROW_ACTION[1]
               .replace("{title}", title).replace("{btn_text}", btn_text))
        self.click(loc)

    # ================= 新建任务 =================
    def open_create_dialog(self):
        self.click(self.BTN_CREATE)
        self.visible(self.CREATE_DIALOG_TITLE)

    def fill_create_form(self, title: str, assignee_name: str, deadline: str = "", desc: str = "",
                         priority: str = "中"):
        """
        填写新建任务表单
        :param title: 任务标题
        :param assignee_name: 下拉展示文本，例如 "张开发 (开发)"
        :param deadline: 截止日期 YYYY-MM-DD
        :param desc: 任务描述
        :param priority: 优先级：高 / 中 / 低
        """
        # 标题输入：JS赋值 + 抛input事件，同步v-model
        title_loc = (self.DIALOG_INPUT[0], self.DIALOG_INPUT[1].replace("{label}", "标题"))
        title_input = wait_for_element_clickable(self.driver, title_loc, 8)
        self.driver.execute_script("""
            const el = arguments[0];
            el.value = arguments[1];
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        """, title_input, title)

        if desc:
            desc_loc = (self.DIALOG_TEXTAREA[0], self.DIALOG_TEXTAREA[1].replace("{label}", "描述"))
            desc_input = wait_for_element_clickable(self.driver, desc_loc, 8)
            self.driver.execute_script("""
                const el = arguments[0];
                el.value = arguments[1];
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            """, desc_input, desc)

        # 优先级下拉
        if priority:
            pri_loc = (self.DIALOG_SELECT[0], self.DIALOG_SELECT[1].replace("{label}", "优先级"))
            self.click(pri_loc)
            self._pick_option(priority).click()
            wait_for_element_invisible(self.driver, (By.CSS_SELECTOR, ".el-select-dropdown"))

        # 指派给下拉
        assign_loc = (self.DIALOG_SELECT[0], self.DIALOG_SELECT[1].replace("{label}", "指派给"))
        self.click(assign_loc)
        self._pick_option(assignee_name).click()
        wait_for_element_invisible(self.driver, (By.CSS_SELECTOR, ".el-select-dropdown"))

        # 截止日期
        if deadline:
            dl_loc = (self.DIALOG_INPUT[0], self.DIALOG_INPUT[1].replace("{label}", "截止日期"))
            dl_input = wait_for_element_clickable(self.driver, dl_loc, 8)
            self.driver.execute_script("""
                const el = arguments[0];
                el.value = arguments[1];
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            """, dl_input, deadline)
            wait_for_element_invisible(self.driver, self.DATETIME_POPPER)

    def submit_create(self):
        """提交新建任务弹窗"""
        submit_loc = (By.XPATH, "//div[@role='dialog']//span[normalize-space()='确定']/parent::button")
        btn = self.visible(submit_loc, timeout=10)
        self.driver.execute_script("arguments[0].click();", btn)

    # ================= 抽屉交互 =================
    def get_drawer_hint(self, timeout: float = 5) -> str:
        """获取抽屉底部的提示文案（如：等待项目经理审核）。

        注意：模板是 `<span v-if="drawerHint">`，只要当前状态有其他可执行动作，
        drawerHint 就是空串、span 根本不渲染。所以这里拿不到就返回空串，不抛异常。
        """
        try:
            return self.visible(self.DRAWER_HINT, timeout=timeout).text.strip()
        except Exception:
            return ""

    def click_drawer_action(self, btn_text: str):
        """点击抽屉底部的操作按钮（如：接受任务、提交任务、审核通过等）"""
        loc = (self.DRAWER_BTN[0], self.DRAWER_BTN[1].replace("{btn_text}", btn_text))
        self.click(loc)

    def close_drawer(self, timeout: float = 10):
        """关闭任务详情抽屉（点右上角关闭按钮，失败退化成 ESC）"""
        try:
            self.click(self.DRAWER_CLOSE_BTN)
        except Exception:
            body = self.driver.find_element(By.TAG_NAME, "body")
            body.send_keys(Keys.ESCAPE)
        wait_for_element_invisible(self.driver, self.DRAWER_TITLE, timeout)

    # ================= 弹窗操作 =================
    def submit_action_dialog(self, label: str, reason: str, submit_btn_text: str):
        """通用处理操作类弹窗（如填拒绝原因后确认）"""
        if reason:
            loc = (self.ACTION_DIALOG_TEXTAREA[0], self.ACTION_DIALOG_TEXTAREA[1].replace("{label}", label))
            self.type_text(loc, reason)
        self.click((self.ACTION_DIALOG_SUBMIT[0], self.ACTION_DIALOG_SUBMIT[1].replace("{btn_text}", submit_btn_text)))

    # ================= 确认框操作 =================
    def confirm_message_box(self):
        """处理全局的确认框（如审核通过确认、恢复任务确认）"""
        self.visible(self.MSG_BOX)
        self.click(self.MSG_BOX_CONFIRM)

    # ================= 补充方法 =================
    def cancel_create_dialog(self):
        """取消新建任务弹窗"""
        self.click(self.DIALOG_BTN_CANCEL)
        wait_for_element_invisible(self.driver, self.CREATE_DIALOG_TITLE)

    def task_exists_on_board(self, title: str, timeout: float = 10) -> bool:
        """判断看板上是否存在指定标题任务，断言用"""
        loc = (self.TASK_ROW_TITLE[0], self.TASK_ROW_TITLE[1].replace("{title}", title))
        try:
            wait_for_element_visible(self.driver, loc, timeout)
            return True
        except Exception:
            return False

    def wait_message(self, msg: str, timeout: float = 10, exact: bool = True):
        """等待 ElementPlus 全局 el-message 提示出现。

        exact=True  → 文本完全相等（推荐，能抓到文案不一致）
        exact=False → 只用包含匹配（文案会带后缀时用，如「已接受任务，开始处理吧」）
        """
        loc = self.EL_MESSAGE_TEXT if exact else self.EL_MESSAGE_TEXT_CONTAINS
        return wait_for_element_visible(
            self.driver, (loc[0], loc[1].replace("{msg}", msg)), timeout
        )

    def wait_message_disappear(self, msg: str, timeout: float = 10):
        """等待全局提示消失"""
        loc = (self.EL_MESSAGE_TEXT[0], self.EL_MESSAGE_TEXT[1].replace("{msg}", msg))
        wait_for_element_invisible(self.driver, loc, timeout)

    def wait_row(self, title: str, timeout: float = 10):
        """等待任务行标题元素可见，返回元素"""
        loc = (self.TASK_ROW_TITLE[0], self.TASK_ROW_TITLE[1].replace("{title}", title))
        return wait_for_element_visible(self.driver, loc, timeout)
