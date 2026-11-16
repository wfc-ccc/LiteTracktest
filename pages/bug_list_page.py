"""缺陷管理页 POM。

源码是 src/views/bug/BugList.vue。
包含列表搜索、新建缺陷（含 AI 润色、附件上传）、指派缺陷以及未读状态红框断言。
"""

from __future__ import annotations
import os
from selenium.webdriver.common.by import By

from pages.base_page import BasePage
from utils.waits import wait_for_first_displayed


class BugListPage(BasePage):
    # ================= 1. 顶部搜索区与操作 =================
    INPUT_TITLE = (By.CSS_SELECTOR, ".search-form input[placeholder='请输入标题关键字']")

    # 通用下拉框定位：通过 label 定位相邻的 el-select
    SEARCH_SELECT = (By.XPATH,
                     "//div[contains(@class,'search-form')]//label[contains(., '{label}')]/following-sibling::div//div[contains(@class,'el-select')]")

    BTN_SEARCH = (By.XPATH, "//div[contains(@class,'search-form')]//button[contains(span, '查询')]")
    BTN_RESET = (By.XPATH, "//div[contains(@class,'search-form')]//button[contains(span, '重置')]")
    BTN_CREATE = (By.XPATH, "//div[contains(@class,'action-right')]//button[contains(., '提交缺陷')]")

    # 下拉面板通用选项
    OPTION_DROPDOWN = (By.XPATH, "//li[contains(@class,'el-select-dropdown__item')]//span[text()='{text}']")

    # ================= 2. 表格区域 =================
    ROW_TITLE = (By.XPATH, "//tr[.//td[normalize-space(.)='{title}']]")
    ROW_ACTION_BTN = (By.XPATH, "//tr[.//td[normalize-space(.)='{title}']]//button[contains(., '{btn_text}')]")

    # 未读变更高亮行
    ROW_UPDATED_CLASS = (By.XPATH, "//tr[contains(@class,'bug-row--updated')][.//td[normalize-space(.)='{title}']]")
    # 空状态文案
    EMPTY_TEXT = (By.CSS_SELECTOR, ".el-table__empty-text")

    # ================= 3. 新建缺陷弹窗 =================
    DIALOG_CREATE_TITLE = (By.XPATH, "//div[contains(@class,'el-dialog')]//span[contains(text(), '提交缺陷')]")

    # 弹窗内通用表单项定位 (label-position="top" 的结构)
    CREATE_INPUT = (By.XPATH,
                    "//div[contains(@class,'el-dialog')]//label[contains(., '{label}')]/following-sibling::div//input")
    CREATE_TEXTAREA = (By.XPATH,
                       "//div[contains(@class,'el-dialog')]//label[contains(., '{label}')]/following-sibling::div//textarea")
    CREATE_SELECT = (By.XPATH,
                     "//div[contains(@class,'el-dialog')]//label[contains(., '{label}')]/following-sibling::div//div[contains(@class,'el-select')]")

    # AI 润色按钮
    BTN_AI_OPTIMIZE = (By.XPATH, "//button[contains(span, 'AI 智能润色')]")

    # 附件上传
    UPLOAD_FILE_INPUT = (By.CSS_SELECTOR, ".el-dialog input[type='file']")

    BTN_CREATE_SUBMIT = (By.XPATH, "//div[contains(@class,'el-dialog__footer')]//button[contains(span, '确定')]")
    BTN_CREATE_CANCEL = (By.XPATH, "//div[contains(@class,'el-dialog__footer')]//button[contains(span, '取消')]")

    # ================= 4. 指派缺陷弹窗 =================
    DIALOG_ASSIGN_TITLE = (By.XPATH, "//div[contains(@class,'el-dialog')]//span[contains(text(), '指派缺陷')]")
    ASSIGN_SELECT_USER = (By.XPATH,
                          "//div[contains(@class,'el-dialog')]//label[text()='指派给']/following-sibling::div//div[contains(@class,'el-select')]")
    BTN_ASSIGN_SUBMIT = (By.XPATH, "//div[contains(@class,'el-dialog__footer')]//button[contains(span, '确定')]")

    # ================= 页面动作 =================

    def open(self, project_id: int | None = None) -> None:
        """打开缺陷列表页。如果有 project_id 则进入项目专属缺陷页"""
        path = f"/projects/{project_id}/bugs" if project_id else "/bugs"
        self.open_path(path)
        self.visible(self.BTN_SEARCH)

    # ---------- 搜索与视图断言 ----------

    def search(self, title: str = "", status: str = "", severity: str = "", assignee: str = ""):
        if title:
            self.type_text(self.INPUT_TITLE, title)
        if status:
            self.click((self.SEARCH_SELECT[0], self.SEARCH_SELECT[1].replace("{label}", "状态")))
            opt = (self.OPTION_DROPDOWN[0], self.OPTION_DROPDOWN[1].replace("{text}", status))
            wait_for_first_displayed(self.driver, opt).click()
        if severity:
            self.click((self.SEARCH_SELECT[0], self.SEARCH_SELECT[1].replace("{label}", "严重程度")))
            opt = (self.OPTION_DROPDOWN[0], self.OPTION_DROPDOWN[1].replace("{text}", severity))
            wait_for_first_displayed(self.driver, opt).click()
        if assignee:
            # 注意：DEV/QA 不可见该筛选项
            self.click((self.SEARCH_SELECT[0], self.SEARCH_SELECT[1].replace("{label}", "指派人")))
            opt = (self.OPTION_DROPDOWN[0], self.OPTION_DROPDOWN[1].replace("{text}", assignee))
            wait_for_first_displayed(self.driver, opt).click()

        self.click(self.BTN_SEARCH)

    def get_empty_text(self) -> str:
        """获取表格无数据时的提示语（用于校验 DEV/QA 的差异化文案）"""
        return self.visible(self.EMPTY_TEXT).text.strip()

    def is_row_updated(self, title: str) -> bool:
        """判断指定缺陷行是否有未读红框高亮"""
        loc = (self.ROW_UPDATED_CLASS[0], self.ROW_UPDATED_CLASS[1].replace("{title}", title))
        try:
            self.visible(loc, timeout=2)
            return True
        except Exception:
            return False

    def click_row_action(self, title: str, btn_text: str):
        """点击表格行内的按钮（如：详情、指派）"""
        loc = (self.ROW_ACTION_BTN[0], self.ROW_ACTION_BTN[1].replace("{title}", title).replace("{btn_text}", btn_text))
        self.click(loc)

    # ---------- 新建缺陷弹窗 ----------

    def fill_create_form(
            self,
            title: str,
            project: str,
            description: str,
            assignee: str,
            module: str = "",
            version: str = "",
            env: str = "",
            priority: str = "",
            severity: str = "",
            expected: str = "",
            actual: str = ""
    ):
        # 必填项
        self.type_text((self.CREATE_INPUT[0], self.CREATE_INPUT[1].replace("{label}", "缺陷标题")), title)
        self.type_text((self.CREATE_TEXTAREA[0], self.CREATE_TEXTAREA[1].replace("{label}", "复现步骤")), description)

        # 所属项目
        self.click((self.CREATE_SELECT[0], self.CREATE_SELECT[1].replace("{label}", "所属项目")))
        opt_proj = (self.OPTION_DROPDOWN[0], self.OPTION_DROPDOWN[1].replace("{text}", project))
        wait_for_first_displayed(self.driver, opt_proj).click()

        # 指派给
        self.click((self.CREATE_SELECT[0], self.CREATE_SELECT[1].replace("{label}", "指派给")))
        opt_user = (self.OPTION_DROPDOWN[0], self.OPTION_DROPDOWN[1].replace("{text}", assignee))
        wait_for_first_displayed(self.driver, opt_user).click()

        # 选填项
        if module:
            self.type_text((self.CREATE_INPUT[0], self.CREATE_INPUT[1].replace("{label}", "所属模块")), module)
        if version:
            self.type_text((self.CREATE_INPUT[0], self.CREATE_INPUT[1].replace("{label}", "发现版本")), version)
        if env:
            self.type_text((self.CREATE_INPUT[0], self.CREATE_INPUT[1].replace("{label}", "运行环境")), env)
        if priority:
            self.click((self.CREATE_SELECT[0], self.CREATE_SELECT[1].replace("{label}", "优先级")))
            opt = (self.OPTION_DROPDOWN[0], self.OPTION_DROPDOWN[1].replace("{text}", priority))
            wait_for_first_displayed(self.driver, opt).click()
        if severity:
            self.click((self.CREATE_SELECT[0], self.CREATE_SELECT[1].replace("{label}", "严重程度")))
            opt = (self.OPTION_DROPDOWN[0], self.OPTION_DROPDOWN[1].replace("{text}", severity))
            wait_for_first_displayed(self.driver, opt).click()
        if expected:
            self.type_text((self.CREATE_TEXTAREA[0], self.CREATE_TEXTAREA[1].replace("{label}", "预期结果")), expected)
        if actual:
            self.type_text((self.CREATE_TEXTAREA[0], self.CREATE_TEXTAREA[1].replace("{label}", "实际结果")), actual)

    def click_ai_optimize(self):
        """点击 AI 润色"""
        self.click(self.BTN_AI_OPTIMIZE)
        # AI 润色可能需要等待，后续用例可结合显式等待判断 textarea 的值发生变化

    def upload_attachment(self, file_path: str):
        """上传附件或日志"""
        abs_path = os.path.abspath(file_path)
        self.visible(self.UPLOAD_FILE_INPUT).send_keys(abs_path)
        # 等待上传成功，可结合列表元素出现判断，此处略

    def submit_create(self):
        self.click(self.BTN_CREATE_SUBMIT)

    # ---------- 指派缺陷弹窗 ----------

    def open_assign_dialog(self, title: str):
        self.click_row_action(title, "指派")
        self.visible(self.DIALOG_ASSIGN_TITLE)

    def assign_to(self, assignee_name: str):
        """在指派弹窗中选择开发人员并确定"""
        self.click(self.ASSIGN_SELECT_USER)
        opt = (self.OPTION_DROPDOWN[0], self.OPTION_DROPDOWN[1].replace("{text}", assignee_name))
        wait_for_first_displayed(self.driver, opt).click()
        self.click(self.BTN_ASSIGN_SUBMIT)