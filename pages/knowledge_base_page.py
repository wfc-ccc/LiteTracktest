"""知识库管理页 POM。

源码是 src/views/knowledge/KnowledgeBase.vue。
包含列表搜索、文件上传、查看/编辑抽屉以及文件删除功能。
"""

from __future__ import annotations
import os
from selenium.webdriver.common.by import By

from pages.base_page import BasePage
from utils.waits import wait_for_first_displayed


class KnowledgeBasePage(BasePage):
    # ================= 1. 顶部搜索区与操作 =================
    INPUT_FILENAME = (By.CSS_SELECTOR, ".search-form input[placeholder='搜索文件名']")
    BTN_SEARCH = (By.XPATH, "//button[contains(span, '搜索')]")
    BTN_RESET = (By.XPATH, "//button[contains(span, '重置')]")
    BTN_UPLOAD = (By.XPATH, "//div[contains(@class,'action-right')]//button[contains(., '上传知识')]")

    # ================= 2. 表格区域 =================
    # 表格行动态定位（按文件名）
    ROW_TITLE = (By.XPATH, "//tr[.//td[normalize-space(.)='{filename}']]")
    # 行内按钮
    ROW_ACTION_BTN = (By.XPATH, "//tr[.//td[normalize-space(.)='{filename}']]//button[contains(., '{btn_text}')]")
    # 访问权限标签（仅 ADMIN 可见，第2列）
    ROW_ACCESS_TAG = (By.XPATH, "//tr[.//td[normalize-space(.)='{filename}']]/td[2]//span[contains(@class,'el-tag')]")

    # ================= 3. 上传文件弹窗 =================
    UPLOAD_DIALOG_TITLE = (By.XPATH, "//div[contains(@class,'el-dialog')]//span[contains(text(), '上传知识文件')]")
    UPLOAD_FILE_INPUT = (By.CSS_SELECTOR, ".el-dialog input[type='file']")
    UPLOAD_SELECT_ACCESS = (By.XPATH,
                            "//div[contains(@class,'el-dialog')]//label[contains(., '访问权限')]/following-sibling::div//div[contains(@class,'el-select')]")
    OPTION_DROPDOWN = (By.XPATH, "//li[contains(@class,'el-select-dropdown__item')]//span[contains(text(), '{text}')]")
    UPLOAD_BTN_CONFIRM = (By.XPATH, "//div[contains(@class,'el-dialog__footer')]//button[contains(., '确定上传')]")

    # ================= 4. 查看/编辑抽屉 =================
    DRAWER_TITLE = (By.CSS_SELECTOR, ".drawer-header__title")
    DRAWER_BTN_DOWNLOAD = (By.XPATH, "//div[contains(@class,'drawer-header')]//button[contains(span, '下载文档')]")

    # 文本展示区（非编辑模式）
    DRAWER_CONTENT_TEXT = (By.CSS_SELECTOR, ".content-viewer__text")
    # 编辑区（编辑模式）
    DRAWER_EDIT_TEXTAREA = (By.CSS_SELECTOR, ".content-viewer textarea")

    # 底部按钮
    DRAWER_BTN_COPY = (By.XPATH, "//div[contains(@class,'el-drawer__footer')]//button[contains(span, '复制全文')]")
    DRAWER_BTN_EDIT = (By.XPATH, "//div[contains(@class,'el-drawer__footer')]//button[contains(span, '编辑')]")
    DRAWER_BTN_CLOSE = (By.XPATH, "//div[contains(@class,'el-drawer__footer')]//button[contains(span, '关闭')]")
    DRAWER_BTN_CANCEL = (By.XPATH, "//div[contains(@class,'el-drawer__footer')]//button[contains(span, '取消')]")
    DRAWER_BTN_SAVE = (By.XPATH, "//div[contains(@class,'el-drawer__footer')]//button[contains(span, '保存')]")

    # ================= 5. 全局确认框 =================
    MSG_BOX = (By.CSS_SELECTOR, ".el-message-box")
    MSG_BOX_CONFIRM = (By.CSS_SELECTOR, ".el-message-box__btns .el-button--primary")

    # ================= 页面动作 =================

    def open(self) -> None:
        """打开知识库管理页"""
        self.open_path("/knowledge")  # 请根据实际路由调整
        self.visible(self.BTN_SEARCH)

    # ---------- 搜索区 ----------

    def search(self, filename: str):
        self.type_text(self.INPUT_FILENAME, filename)
        self.click(self.BTN_SEARCH)

    def reset(self):
        self.click(self.BTN_RESET)

    # ---------- 表格与权限断言 ----------

    def get_access_level(self, filename: str) -> str:
        """获取指定文件的访问权限标签文本（仅 ADMIN 视图存在）"""
        loc = (self.ROW_ACCESS_TAG[0], self.ROW_ACCESS_TAG[1].replace("{filename}", filename))
        return self.visible(loc).text.strip()

    def click_row_action(self, filename: str, btn_text: str):
        """点击行内操作按钮（如：查看、删除）"""
        loc = (self.ROW_ACTION_BTN[0],
               self.ROW_ACTION_BTN[1].replace("{filename}", filename).replace("{btn_text}", btn_text))
        self.click(loc)

    # ---------- 文件上传 ----------

    def open_upload_dialog(self):
        self.click(self.BTN_UPLOAD)
        self.visible(self.UPLOAD_DIALOG_TITLE)

    def upload_file(self, file_path: str, access_level: str = "全员访问"):
        """
        上传文件。
        :param file_path: 本地文件的绝对路径
        :param access_level: 下拉选项文本（如"全员访问"、"AI 可检索"、"仅管理员"）
        """
        # 1. 上传文件（直接向隐藏的 input type=file 发送绝对路径）
        abs_path = os.path.abspath(file_path)
        self.visible(self.UPLOAD_FILE_INPUT).send_keys(abs_path)

        # 2. 选择访问权限
        if access_level:
            self.click(self.UPLOAD_SELECT_ACCESS)
            opt = (self.OPTION_DROPDOWN[0], self.OPTION_DROPDOWN[1].replace("{text}", access_level))
            wait_for_first_displayed(self.driver, opt).click()

        # 3. 点击确定上传
        self.click(self.UPLOAD_BTN_CONFIRM)

    # ---------- 抽屉交互 ----------

    def get_drawer_content(self) -> str:
        """获取抽屉中展示的纯文本内容"""
        return self.visible(self.DRAWER_CONTENT_TEXT).text.strip()

    def edit_drawer_content(self, new_content: str):
        """点击编辑并修改内容"""
        self.click(self.DRAWER_BTN_EDIT)
        textarea = self.visible(self.DRAWER_EDIT_TEXTAREA)
        textarea.clear()
        textarea.send_keys(new_content)
        self.click(self.DRAWER_BTN_SAVE)

    def close_drawer(self):
        """关闭抽屉"""
        self.click(self.DRAWER_BTN_CLOSE)

    # ---------- 删除文件 ----------

    def delete_file(self, filename: str):
        """点击删除并处理全局确认框"""
        self.click_row_action(filename, "删除")
        self.visible(self.MSG_BOX)
        self.click(self.MSG_BOX_CONFIRM)