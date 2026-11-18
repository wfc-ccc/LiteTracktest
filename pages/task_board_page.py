"""任务看板 POM。
源码是 src/views/task/TaskBoard.vue。
包含了极高的状态流转、复杂的筛选、抽屉面板及多个操作弹窗。
"""
from __future__ import annotations
from selenium.webdriver.common.by import By

from pages.base_page import BasePage
from utils.waits import (
    wait_for_element_visible,
    wait_for_element_clickable,
    wait_for_element_invisible,
    wait_for_first_displayed
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
    TASK_ROW_TITLE = (By.XPATH, "//span[contains(@class,'task-title-link') and normalize-space(.)='{title}']")
    TASK_ROW_ACTION = (By.XPATH, "//tr[.//span[contains(@class,'task-title-link') and normalize-space(.)='{title}']]//button[contains(., '{btn_text}')]")
    # 状态位于该行第 2 列
    TASK_ROW_STATUS = (By.XPATH, "//tr[.//span[contains(@class,'task-title-link')] and normalize-space(.)='{title}']/td[2]//span[contains(@class,'el-tag')]")

    # ================= 3. 新建任务弹窗 =================
    CREATE_DIALOG_TITLE = (By.XPATH, "//div[contains(@class,'el-dialog')]//span[contains(@class,'el-dialog__title') and contains(., '新建任务')]")
    # 通用表单输入（根据 label 定位同级的 input 或 textarea）
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
    # 抽屉底部操作按钮
    DRAWER_BTN = (By.XPATH, "//div[contains(@class,'drawer-footer__actions')]//button[contains(., '{btn_text}')]")
    DRAWER_BLOCK_CARD = (By.CSS_SELECTOR, ".block-card")

    # ================= 5. 全局确认框 (MessageBox) =================
    MSG_BOX = (By.CSS_SELECTOR, ".el-message-box")
    MSG_BOX_CONFIRM = (By.CSS_SELECTOR, ".el-message-box__btns .el-button--primary")

    # ================= 6. 全局 el-message 提示 =================
    EL_MESSAGE = (By.CSS_SELECTOR, ".el-message")
    EL_MESSAGE_TEXT = (By.XPATH, "//div[contains(@class,'el-message')]//p[normalize-space()='{msg}']")

    # ================= 7. 各种操作弹窗 =================
    # 弹窗内通用 textarea
    ACTION_DIALOG_TEXTAREA = (By.XPATH, "//div[contains(@class,'el-dialog')]//label[contains(., '{label}')]/following-sibling::div//textarea")
    # 弹窗内通用提交按钮（按文字匹配，如“确认拒绝”、“提交”、“确认阻塞”等）
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

    # ================= 筛选操作 =================
    def search(self, keyword: str = "", status: str = "", assignee: str = ""):
        if keyword:
            self.type_text(self.FILTER_INPUT_KEYWORD, keyword)
        if status:
            self.click(self.FILTER_SELECT_STATUS)
            opt = (self.OPTION_DROPDOWN[0], self.OPTION_DROPDOWN[1].replace("{text}", status))
            wait_for_first_displayed(self.driver, opt).click()
        if assignee:
            self.click(self.FILTER_SELECT_ASSIGNEE)
            opt = (self.OPTION_DROPDOWN[0], self.OPTION_DROPDOWN[1].replace("{text}", assignee))
            wait_for_first_displayed(self.driver, opt).click()
        self.click(self.BTN_SEARCH)

    def reset(self):
        self.click(self.BTN_RESET)

    # ================= 表格与行内操作 =================
    def get_task_status(self, title: str) -> str:
        """获取列表中指定任务的当前状态"""
        loc = (self.TASK_ROW_STATUS[0], self.TASK_ROW_STATUS[1].replace("{title}", title))
        return self.visible(loc).text.strip()

    def click_task_title(self, title: str):
        """点击表格中的任务标题，打开抽屉"""
        loc = (self.TASK_ROW_TITLE[0], self.TASK_ROW_TITLE[1].replace("{title}", title))
        self.click(loc)
        self.visible(self.DRAWER_TITLE)

    def click_row_action(self, title: str, btn_text: str):
        """点击表格某行的操作按钮（如：详情、删除）"""
        loc = (self.TASK_ROW_ACTION[0], self.TASK_ROW_ACTION[1].replace("{title}", title).replace("{btn_text}", btn_text))
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
            el.dispatchEvent(new Event('input'));
        """, title_input, title)

        if desc:
            desc_loc = (self.DIALOG_TEXTAREA[0], self.DIALOG_TEXTAREA[1].replace("{label}", "描述"))
            desc_input = wait_for_element_clickable(self.driver, desc_loc, 8)
            self.driver.execute_script("""
                const el = arguments[0];
                el.value = arguments[1];
                el.dispatchEvent(new Event('input'));
            """, desc_input, desc)

        # 优先级下拉
        if priority:
            pri_loc = (self.DIALOG_SELECT[0], self.DIALOG_SELECT[1].replace("{label}", "优先级"))
            self.click(pri_loc)
            opt = (self.OPTION_DROPDOWN[0], self.OPTION_DROPDOWN[1].replace("{text}", priority))
            wait_for_first_displayed(self.driver, opt).click()
            wait_for_element_invisible(self.driver, (By.CSS_SELECTOR, ".el-select-dropdown"))

        # 指派给下拉
        assign_loc = (self.DIALOG_SELECT[0], self.DIALOG_SELECT[1].replace("{label}", "指派给"))
        self.click(assign_loc)
        opt = (self.OPTION_DROPDOWN[0], self.OPTION_DROPDOWN[1].replace("{text}", assignee_name))
        wait_for_first_displayed(self.driver, opt).click()
        wait_for_element_invisible(self.driver, (By.CSS_SELECTOR, ".el-select-dropdown"))

        # 截止日期
        if deadline:
            dl_loc = (self.DIALOG_INPUT[0], self.DIALOG_INPUT[1].replace("{label}", "截止日期"))
            dl_input = wait_for_element_clickable(self.driver, dl_loc, 8)
            self.driver.execute_script("""
                const el = arguments[0];
                el.value = arguments[1];
                el.dispatchEvent(new Event('input'));
            """, dl_input, deadline)
            wait_for_element_invisible(self.driver, self.DATETIME_POPPER)

    def submit_create(self):
        """提交新建任务弹窗"""
        submit_loc = (By.XPATH, "//div[@role='dialog']//span[normalize-space()='确定']/parent::button")
        btn = self.visible(submit_loc, timeout=10)
        self.driver.execute_script("arguments[0].click();", btn)

    # ================= 抽屉交互 =================
    def get_drawer_hint(self) -> str:
        """获取抽屉底部的提示文案（如：等待项目经理审核）"""
        return self.visible(self.DRAWER_HINT).text.strip()

    def click_drawer_action(self, btn_text: str):
        """点击抽屉底部的操作按钮（如：接受任务、提交任务、审核通过等）"""
        loc = (self.DRAWER_BTN[0], self.DRAWER_BTN[1].replace("{btn_text}", btn_text))
        self.click(loc)

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

    # ========== 【新增补充方法，方便后续用例全覆盖】 ==========
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

    def wait_message(self, msg: str, timeout: float = 10):
        """等待 ElementPlus 全局 el-message 提示出现（精确文本匹配）"""
        loc = (self.EL_MESSAGE_TEXT[0], self.EL_MESSAGE_TEXT[1].replace("{msg}", msg))
        return wait_for_element_visible(self.driver, loc, timeout)

    def wait_message_disappear(self, msg: str, timeout: float = 10):
        """等待全局提示消失"""
        loc = (self.EL_MESSAGE_TEXT[0], self.EL_MESSAGE_TEXT[1].replace("{msg}", msg))
        wait_for_element_invisible(self.driver, loc, timeout)

    def wait_row(self, title: str, timeout: float = 10):
        """等待任务行标题元素可见，返回元素"""
        loc = (self.TASK_ROW_TITLE[0], self.TASK_ROW_TITLE[1].replace("{title}", title))
        return wait_for_element_visible(self.driver, loc, timeout)

