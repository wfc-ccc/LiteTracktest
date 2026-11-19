"""项目管理页 POM。

源码是 src/views/project/ProjectList.vue。
覆盖：列表搜索、行内权限操作、新建/编辑项目（含多选成员）、成员管理弹窗及二次确认。
"""

from __future__ import annotations

from selenium.webdriver.common.by import By

from pages.base_page import BasePage
from utils.waits import wait_for_first_displayed, wait_for_element_visible


class ProjectManagePage(BasePage):
    # ================= 1. 顶部搜索区 =================
    INPUT_NAME = (By.CSS_SELECTOR, ".search-form input[placeholder='请输入项目名称']")
    SELECT_STATUS = (By.XPATH,
                     "//div[contains(@class,'search-form')]//label[contains(., '状态')]/following-sibling::div//div[contains(@class,'el-select')]")
    OPTION_DROPDOWN = (By.XPATH, "//li[contains(@class,'el-select-dropdown__item')]//span[text()='{text}']")

    BTN_SEARCH = (By.XPATH, "//button[contains(span, '查询')]")
    BTN_RESET = (By.XPATH, "//button[contains(span, '重置')]")
    BTN_CREATE = (By.XPATH, "//div[contains(@class,'action-right')]//button[contains(., '新建项目')]")

    # ================= 2. 表格区域 =================
    # 根据项目名称定位行
    ROW_TITLE = (By.XPATH, "//tr[.//td[normalize-space(.)='{project_name}']]")
    # 定位行内的特定按钮（如：任务、缺陷、编辑、关闭、删除等）
    ROW_ACTION_BTN = (By.XPATH, "//tr[.//td[normalize-space(.)='{project_name}']]//button[contains(., '{btn_text}')]")
    # 获取行的状态标签（第 5 列）
    ROW_STATUS = (By.XPATH, "//tr[.//td[normalize-space(.)='{project_name}']]/td[5]//span[contains(@class,'el-tag')]")

    # ================= 3. 新建/编辑项目弹窗 =================
    DIALOG_TITLE = (By.XPATH, "//div[contains(@class,'el-dialog')]//span[contains(@class,'el-dialog__title')]")
    # 通用表单输入（根据 label 定位）
    DIALOG_INPUT = (By.XPATH,
                    "//div[contains(@class,'el-dialog')]//label[contains(., '{label}')]/following-sibling::div//input")
    DIALOG_TEXTAREA = (By.XPATH,
                       "//div[contains(@class,'el-dialog')]//label[contains(., '{label}')]/following-sibling::div//textarea")
    DIALOG_SELECT = (By.XPATH,
                     "//div[contains(@class,'el-dialog')]//label[contains(., '{label}')]/following-sibling::div//div[contains(@class,'el-select')]")

    DIALOG_BTN_SUBMIT = (By.XPATH, "//div[contains(@class,'el-dialog__footer')]//button[contains(span, '确定')]")
    DIALOG_BTN_CANCEL = (By.XPATH, "//div[contains(@class,'el-dialog__footer')]//button[contains(span, '取消')]")

    # ================= 4. 成员管理弹窗 =================
    MEMBER_DIALOG_LABEL = (By.CSS_SELECTOR, ".member-dialog__label")
    MEMBER_TAGS = (By.CSS_SELECTOR, ".member-dialog__tags .el-tag")
    MEMBER_TAG_BY_NAME = (By.XPATH, "//div[contains(@class,'member-dialog__tags')]//span[contains(., '{name}')]")
    # 成员添加下拉框
    MEMBER_ADD_SELECT = (By.CSS_SELECTOR, ".member-dialog__add .el-select")
    BTN_MEMBER_ADD = (By.XPATH, "//div[contains(@class,'member-dialog__add')]//button[contains(span, '添加')]")
    # 只读提示
    MEMBER_READONLY_TIP = (By.XPATH,
                           "//div[contains(@class,'el-alert')]//span[contains(text(), '项目已关闭，成员信息仅供查看')]")

    # ================= 5. 全局 MessageBox =================
    MSG_BOX = (By.CSS_SELECTOR, ".el-message-box")
    MSG_BOX_CONFIRM = (By.CSS_SELECTOR, ".el-message-box__btns .el-button--primary")

    # ================= 页面动作 =================

    def open(self) -> None:
        """打开项目管理页"""
        self.open_path("/projects")
        # 🌟 修复：不能等 BTN_CREATE，因为 QA 没权限看这个按钮。
        # 换成等待所有角色可见的通用搜索输入框出现
        self.visible(self.INPUT_NAME)

    # ---------- 搜索与表格 ----------

    def search(self, name: str = "", status_text: str = ""):
        if name:
            self.type_text(self.INPUT_NAME, name)
        if status_text:
            self.click(self.SELECT_STATUS)
            opt = (self.OPTION_DROPDOWN[0], self.OPTION_DROPDOWN[1].replace("{text}", status_text))
            wait_for_first_displayed(self.driver, opt).click()
        self.click(self.BTN_SEARCH)

    def get_project_status(self, project_name: str) -> str:
        """获取指定项目的状态标签文字"""
        loc = (self.ROW_STATUS[0], self.ROW_STATUS[1].replace("{project_name}", project_name))
        return self.visible(loc).text.strip()

    def click_row_action(self, project_name: str, btn_text: str):
        """点击表格行内的操作按钮（如：任务、缺陷、编辑、成员、关闭）"""
        loc = (self.ROW_ACTION_BTN[0],
               self.ROW_ACTION_BTN[1].replace("{project_name}", project_name).replace("{btn_text}", btn_text))
        self.click(loc)

    def is_row_action_exist(self, project_name: str, btn_text: str) -> bool:
        """判断某行是否存在特定的操作按钮（用于测试权限隔离）"""
        loc = (self.ROW_ACTION_BTN[0],
               self.ROW_ACTION_BTN[1].replace("{project_name}", project_name).replace("{btn_text}", btn_text))
        try:
            self.visible(loc, timeout=2)
            return True
        except Exception:
            return False

    # ---------- 新建/编辑项目弹窗 ----------

    def fill_project_form(self, name: str = None, desc: str = None, owner: str = None, members: list[str] = None):
        """填写项目表单。owner 仅 ADMIN 可见；members 是列表"""
        if name is not None:
            self.type_text((self.DIALOG_INPUT[0], self.DIALOG_INPUT[1].replace("{label}", "项目名称")), name)
        if desc is not None:
            self.type_text((self.DIALOG_TEXTAREA[0], self.DIALOG_TEXTAREA[1].replace("{label}", "描述")), desc)

        if owner:
            self.click((self.DIALOG_SELECT[0], self.DIALOG_SELECT[1].replace("{label}", "负责人")))
            opt = (self.OPTION_DROPDOWN[0], self.OPTION_DROPDOWN[1].replace("{text}", owner))
            wait_for_first_displayed(self.driver, opt).click()

        if members:
            self.click((self.DIALOG_SELECT[0], self.DIALOG_SELECT[1].replace("{label}", "项目成员")))
            for member in members:
                opt = (self.OPTION_DROPDOWN[0], self.OPTION_DROPDOWN[1].replace("{text}", member))
                wait_for_first_displayed(self.driver, opt).click()
            # 点击空白处收起下拉框，避免遮挡确定按钮
            self.visible(self.DIALOG_TITLE).click()

    def submit_project_dialog(self):
        self.click(self.DIALOG_BTN_SUBMIT)

    # ---------- 成员管理弹窗 ----------

    def get_member_count(self) -> int:
        """获取现有成员标签的数量"""
        self.visible(self.MEMBER_DIALOG_LABEL)
        return len(self.driver.find_elements(*self.MEMBER_TAGS))

    def is_member_exist(self, name: str) -> bool:
        """判断成员弹窗中是否存在特定名字的标签"""
        loc = (self.MEMBER_TAG_BY_NAME[0], self.MEMBER_TAG_BY_NAME[1].replace("{name}", name))
        try:
            self.visible(loc, timeout=2)
            return True
        except Exception:
            return False

    def add_members(self, members: list[str]):
        """在成员弹窗中添加新成员"""
        self.click(self.MEMBER_ADD_SELECT)
        for member in members:
            opt = (self.OPTION_DROPDOWN[0], self.OPTION_DROPDOWN[1].replace("{text}", member))
            wait_for_first_displayed(self.driver, opt).click()
        # 点击空白处收起下拉框
        self.visible(self.MEMBER_DIALOG_LABEL).click()
        self.click(self.BTN_MEMBER_ADD)

    def remove_member(self, name: str):
        """点击成员标签上的 x 号移除成员"""
        # Element Plus 的关闭图标在 el-tag 内部的 .el-tag__close
        loc = (By.XPATH,
               f"//div[contains(@class,'member-dialog__tags')]//span[contains(., '{name}')]/i[contains(@class,'el-tag__close')]")
        self.click(loc)

    def is_member_readonly(self) -> bool:
        """判断成员弹窗是否为只读模式（项目已关闭）"""
        try:
            return self.visible(self.MEMBER_READONLY_TIP, timeout=2).is_displayed()
        except Exception:
            return False

    # ---------- 确认框 ----------

    def confirm_message_box(self):
        self.visible(self.MSG_BOX)
        self.click(self.MSG_BOX_CONFIRM)