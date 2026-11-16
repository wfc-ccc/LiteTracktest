"""用户管理页 POM。

源码是 src/views/user/UserManage.vue。
覆盖：视图切换、搜索、新建/编辑弹窗、行内操作（删除、恢复、彻底删除等）及 MessageBox 确认。
"""

from __future__ import annotations

from selenium.webdriver.common.by import By

from pages.base_page import BasePage
from utils.waits import wait_for_first_displayed, wait_for_element_visible


class UserManagePage(BasePage):
    # ================= 元素定位器 =================

    # 1. 视图切换
    RADIO_NORMAL = (By.XPATH, "//label[contains(@class, 'el-radio-button')]//span[contains(text(), '正常用户')]")
    RADIO_DELETED = (By.XPATH, "//label[contains(@class, 'el-radio-button')]//span[contains(text(), '已删除用户')]")

    # 2. 搜索区
    INPUT_USERNAME = (By.CSS_SELECTOR, "input[placeholder='请输入用户名']")
    SELECT_ROLE = (By.XPATH,
                   "//div[contains(@class, 'el-form-item')][.//label[text()='角色']]//div[contains(@class, 'el-select')]")
    SELECT_STATUS = (By.XPATH,
                     "//div[contains(@class, 'el-form-item')][.//label[text()='状态']]//div[contains(@class, 'el-select')]")
    # 下拉面板选项（通用）
    OPTION_SELECT = (By.XPATH, "//li[contains(@class, 'el-select-dropdown__item')]//span[text()='{text}']")

    BTN_SEARCH = (By.XPATH, "//button[contains(span, '查询')]")
    BTN_RESET = (By.XPATH, "//button[contains(span, '重置')]")
    BTN_CREATE = (By.XPATH, "//button[contains(span, '新建用户')]")

    # 3. 表格与行内操作（根据用户名定位行）
    ROW_BY_USERNAME = (By.XPATH, "//tr[.//td[normalize-space(.)='{username}']]")
    # 行内按钮定位（拼接时使用）
    BTN_IN_ROW = (By.XPATH, "//tr[.//td[normalize-space(.)='{username}']]//button[contains(., '{btn_text}')]")
    # 状态标签
    TAG_STATUS = (By.XPATH,
                  "//tr[.//td[normalize-space(.)='{username}']]/td[contains(@class, 'el-table_1_column_5')]//span[contains(@class, 'el-tag')]")

    # 4. 弹窗 (新建/编辑)
    DIALOG_TITLE = (By.XPATH, "//div[contains(@class, 'el-dialog')]//span[contains(@class, 'el-dialog__title')]")
    # Element Plus 表单项的通用定位：根据 label 找对应的 input
    DIALOG_INPUT = (By.XPATH,
                    "//div[contains(@class, 'el-dialog')]//label[text()='{label}']/following-sibling::div//input")
    DIALOG_SELECT_ROLE = (By.XPATH,
                          "//div[contains(@class, 'el-dialog')]//label[text()='角色']/following-sibling::div//div[contains(@class, 'el-select')]")
    DIALOG_BTN_SUBMIT = (By.XPATH, "//div[contains(@class, 'el-dialog__footer')]//button[contains(span, '确定')]")
    DIALOG_BTN_CANCEL = (By.XPATH, "//div[contains(@class, 'el-dialog__footer')]//button[contains(span, '取消')]")

    # 5. MessageBox 确认框 (全局挂载)
    MSG_BOX = (By.CSS_SELECTOR, ".el-message-box")
    MSG_BOX_CONFIRM = (By.CSS_SELECTOR, ".el-message-box__btns .el-button--primary")

    # ================= 页面动作 =================

    def open(self) -> None:
        """打开用户管理页"""
        self.open_path("/users")  # 假设你的路由是 /users，可根据实际调整
        self.visible(self.BTN_CREATE)

    # ---------- 视图与搜索 ----------

    def switch_view(self, mode: str):
        """切换视图: 'normal' 或 'deleted'"""
        if mode == "normal":
            self.click(self.RADIO_NORMAL)
        elif mode == "deleted":
            self.click(self.RADIO_DELETED)
        else:
            raise ValueError("mode 必须是 'normal' 或 'deleted'")

    def search(self, username: str = "", role_text: str = "", status_text: str = ""):
        """组合条件搜索"""
        if username:
            self.type_text(self.INPUT_USERNAME, username)

        if role_text:
            self.click(self.SELECT_ROLE)
            option = (self.OPTION_SELECT[0], self.OPTION_SELECT[1].replace("{text}", role_text))
            wait_for_first_displayed(self.driver, option).click()

        if status_text:
            self.click(self.SELECT_STATUS)
            option = (self.OPTION_SELECT[0], self.OPTION_SELECT[1].replace("{text}", status_text))
            wait_for_first_displayed(self.driver, option).click()

        self.click(self.BTN_SEARCH)

    def reset_search(self):
        """点击重置"""
        self.click(self.BTN_RESET)

    # ---------- 弹窗与表单 ----------

    def open_create_dialog(self):
        self.click(self.BTN_CREATE)
        self.visible(self.DIALOG_TITLE)

    def fill_form(self, username: str = None, password: str = None, real_name: str = None, role_text: str = None):
        """填写新建或编辑表单"""
        if username is not None:
            el = self.visible((self.DIALOG_INPUT[0], self.DIALOG_INPUT[1].replace("{label}", "用户名")))
            if not el.get_attribute("disabled"):  # 编辑模式下用户名不可改
                self.type_text((self.DIALOG_INPUT[0], self.DIALOG_INPUT[1].replace("{label}", "用户名")), username)

        if password is not None:
            self.type_text((self.DIALOG_INPUT[0], self.DIALOG_INPUT[1].replace("{label}", "密码")), password)

        if real_name is not None:
            self.type_text((self.DIALOG_INPUT[0], self.DIALOG_INPUT[1].replace("{label}", "真实姓名")), real_name)

        if role_text is not None:
            self.click(self.DIALOG_SELECT_ROLE)
            option = (self.OPTION_SELECT[0], self.OPTION_SELECT[1].replace("{text}", role_text))
            wait_for_first_displayed(self.driver, option).click()

    def submit_dialog(self):
        self.click(self.DIALOG_BTN_SUBMIT)
        # 等待弹窗消失
        wait_for_element_visible(self.driver, (By.CSS_SELECTOR, ".el-overlay"), timeout=2)  # 可能需要调整为 invisibility

    # ---------- 行内操作 ----------

    def click_row_action(self, username: str, btn_text: str):
        """点击某行的特定按钮（如：编辑、禁用、删除、恢复、彻底删除）"""
        loc = (self.BTN_IN_ROW[0], self.BTN_IN_ROW[1].replace("{username}", username).replace("{btn_text}", btn_text))
        self.click(loc)

    def get_row_status(self, username: str) -> str:
        """获取某行状态标签的文字（启用、禁用、已删除）"""
        loc = (self.TAG_STATUS[0], self.TAG_STATUS[1].replace("{username}", username))
        return self.visible(loc).text.strip()

    def is_action_btn_exist(self, username: str, btn_text: str) -> bool:
        """判断某行是否有特定按钮（用于测试 admin 账号没有删除按钮）"""
        loc = (self.BTN_IN_ROW[0], self.BTN_IN_ROW[1].replace("{username}", username).replace("{btn_text}", btn_text))
        try:
            self.visible(loc, timeout=2)
            return True
        except Exception:
            return False

    # ---------- MessageBox 确认 ----------

    def confirm_message_box(self):
        """点击 Element Plus 弹框的『确定』按钮"""
        self.visible(self.MSG_BOX)
        self.click(self.MSG_BOX_CONFIRM)
        # 等待消失

    def get_message_box_text(self) -> str:
        """获取弹框文本（用于断言警告文案）"""
        self.visible(self.MSG_BOX)
        return self.driver.find_element(By.CSS_SELECTOR, ".el-message-box__message").text.strip()