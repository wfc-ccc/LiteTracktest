"""缺陷详情页 POM。

源码是 src/views/bug/BugDetail.vue。
涉及：只读判断、基础信息断言、流转时间轴断言，以及修复/验证/打回/重指派四大弹窗操作。
"""

from __future__ import annotations
import os
from selenium.webdriver.common.by import By

from pages.base_page import BasePage
from utils.waits import wait_for_first_displayed


class BugDetailPage(BasePage):
    # ================= 1. 顶部 Header 与操作区 =================
    BUG_TITLE = (By.CSS_SELECTOR, ".bug-header__title")
    STATUS_TAG = (By.CSS_SELECTOR, ".bug-header__tags .el-tag:nth-child(1)")
    SEVERITY_TAG = (By.CSS_SELECTOR, ".bug-header__tags .el-tag:nth-child(2)")
    READONLY_TIP = (By.CSS_SELECTOR, ".readonly-tip")

    # 顶部操作按钮（标记已修复、验证关闭等）
    HEADER_ACTION_BTN = (By.XPATH,
                         "//div[contains(@class,'bug-header__actions')]//button[contains(span, '{btn_text}')]")

    # ================= 2. 详情卡片与内容 =================
    # 根据卡片标题定位整个卡片区域
    CARD_BY_TITLE = (By.XPATH,
                     "//div[contains(@class,'detail-card')][.//div[contains(@class,'card-header')]//span[contains(., '{title}')]]")

    # 基础属性（label 和 value）
    BASE_FIELD_VALUE = (By.XPATH,
                        "//div[contains(@class,'base-info')]//td[contains(@class,'el-descriptions__label')][contains(., '{label}')]/following-sibling::td")

    # 内容块（复现步骤、预期结果等）
    CONTENT_BLOCK_BODY = (By.XPATH,
                          "//div[contains(@class,'content-block')][.//div[contains(@class,'content-block__title') and contains(., '{title}')]]//div[contains(@class,'content-block__body')]")

    # 附件
    ATTACHMENT_IMAGE = (By.CSS_SELECTOR, ".attachment-images .attachment-thumb")
    ATTACHMENT_FILE = (By.CSS_SELECTOR, ".attachment-files .file-link")

    # ================= 3. 流转时间轴 =================
    TIMELINE_ITEMS = (By.CSS_SELECTOR, ".timeline-item")
    TIMELINE_ITEM_TAG = (By.XPATH, ".//div[contains(@class,'timeline-item__header')]//span[contains(@class,'el-tag')]")

    # ================= 4. 弹窗（通用表单项定位） =================
    DIALOG_TITLE = (By.CSS_SELECTOR, ".el-dialog__title")
    # 根据 label 查找同级或下方的 input/textarea
    DIALOG_INPUT = (By.XPATH,
                    "//div[contains(@class,'el-dialog')]//label[contains(., '{label}')]/following-sibling::div//input")
    DIALOG_TEXTAREA = (By.XPATH,
                       "//div[contains(@class,'el-dialog')]//label[contains(., '{label}')]/following-sibling::div//textarea")
    DIALOG_SELECT = (By.XPATH,
                     "//div[contains(@class,'el-dialog')]//label[contains(., '{label}')]/following-sibling::div//div[contains(@class,'el-select')]")
    DIALOG_RADIO = (By.XPATH,
                    "//div[contains(@class,'el-dialog')]//label[contains(., '验证结果')]/following-sibling::div//label[contains(., '{text}')]")

    # 弹窗内文件上传
    DIALOG_FILE_INPUT = (By.CSS_SELECTOR, ".el-dialog input[type='file']")

    # 弹窗底部按钮
    DIALOG_FOOTER_BTN = (By.XPATH, "//div[contains(@class,'el-dialog__footer')]//button[contains(span, '{btn_text}')]")

    # ================= 页面初始化与读取动作 =================

    def open(self, bug_id: int) -> None:
        """打开指定缺陷的详情页"""
        self.open_path(f"/bugs/{bug_id}")
        self.visible(self.BUG_TITLE)

    def is_readonly(self) -> bool:
        """判断项目是否已关闭，处于只读模式"""
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
        """获取基础属性值（如：提交人、指派人、所属项目）"""
        loc = (self.BASE_FIELD_VALUE[0], self.BASE_FIELD_VALUE[1].replace("{label}", label))
        return self.visible(loc).text.strip()

    def get_content_block(self, title: str) -> str:
        """获取内容块的值（如：复现步骤、预期结果）"""
        loc = (self.CONTENT_BLOCK_BODY[0], self.CONTENT_BLOCK_BODY[1].replace("{title}", title))
        return self.visible(loc).text.strip()

    # ================= 流转操作与弹窗 =================

    def is_action_exist(self, btn_text: str) -> bool:
        """判断顶部操作按钮是否存在（用于断言权限/状态隔离）"""
        loc = (self.HEADER_ACTION_BTN[0], self.HEADER_ACTION_BTN[1].replace("{btn_text}", btn_text))
        try:
            self.visible(loc, timeout=2)
            return True
        except Exception:
            return False

    def click_header_action(self, btn_text: str):
        """点击顶部操作按钮（如：标记已修复、验证关闭、重新激活、重新指派）"""
        loc = (self.HEADER_ACTION_BTN[0], self.HEADER_ACTION_BTN[1].replace("{btn_text}", btn_text))
        self.click(loc)

    def _fill_dialog_input(self, label: str, value: str):
        self.type_text((self.DIALOG_INPUT[0], self.DIALOG_INPUT[1].replace("{label}", label)), value)

    def _fill_dialog_textarea(self, label: str, value: str):
        self.type_text((self.DIALOG_TEXTAREA[0], self.DIALOG_TEXTAREA[1].replace("{label}", label)), value)

    def _click_dialog_btn(self, btn_text: str):
        self.click((self.DIALOG_FOOTER_BTN[0], self.DIALOG_FOOTER_BTN[1].replace("{btn_text}", btn_text)))

    def upload_dialog_attachment(self, file_path: str):
        """在弹窗中上传附件"""
        abs_path = os.path.abspath(file_path)
        self.visible(self.DIALOG_FILE_INPUT).send_keys(abs_path)
        # 可补充等待上传成功的逻辑

    # --- 具体业务弹窗封装 ---

    def submit_fix_report(self, root_cause: str, version: str, self_test: str, impact: str = "", risks: str = "",
                          file_path: str = None):
        """[DEV] 提交修复报告"""
        self.click_header_action("标记已修复")
        self.visible(self.DIALOG_TITLE)  # 等待弹窗

        self._fill_dialog_textarea("根因与修复说明", root_cause)
        self._fill_dialog_input("修复版本/提交", version)
        self._fill_dialog_textarea("自测结果", self_test)
        if impact:
            self._fill_dialog_textarea("影响范围/回归建议", impact)
        if risks:
            self._fill_dialog_textarea("风险/限制", risks)
        if file_path:
            self.upload_dialog_attachment(file_path)

        self._click_dialog_btn("提交修复报告")

    def submit_qa_verification(self, result: str = "验证通过", steps: str = "", file_path: str = None):
        """
        [QA] 提交测试验证报告
        :param result: '验证通过' 或 '回归不通过'
        """
        if "重新激活" in result:
            self.click_header_action("重新激活")
        else:
            self.click_header_action("验证关闭")
        self.visible(self.DIALOG_TITLE)

        # 选择单选框
        radio_loc = (self.DIALOG_RADIO[0], self.DIALOG_RADIO[1].replace("{text}", result))
        self.click(radio_loc)

        self._fill_dialog_textarea("测试验证步骤", steps)
        if file_path:
            self.upload_dialog_attachment(file_path)

        # 按钮文案不同
        btn_text = "提交测试报告" if "通过" in result and "不通过" not in result else "确认打回"
        # 注意：打回其实走的是另一个弹窗（reopen-dialog），但前端把入口合并了。
        # 为了 POM 的健壮性，这里根据按钮名点
        if btn_text == "确认打回":
            self._click_dialog_btn("确认打回")
        else:
            self._click_dialog_btn("提交测试报告")

    def submit_reopen_report(self, reason_type: str, reason_desc: str, env: str, expected: str, actual: str,
                             steps: str):
        """[QA] 填写完整的打回单 (通过顶部重新激活按钮进入)"""
        self.click_header_action("重新激活")
        self.visible(self.DIALOG_TITLE)

        # 下拉框选择分类
        self.click((self.DIALOG_SELECT[0], self.DIALOG_SELECT[1].replace("{label}", "打回原因分类")))
        opt = (By.XPATH, f"//li[contains(@class,'el-select-dropdown__item')]//span[text()='{reason_type}']")
        wait_for_first_displayed(self.driver, opt).click()

        self._fill_dialog_textarea("打回详细说明", reason_desc)
        self._fill_dialog_input("验证版本与环境", env)
        self._fill_dialog_textarea("预期结果", expected)
        self._fill_dialog_textarea("实际结果", actual)
        self._fill_dialog_textarea("复现步骤与测试数据", steps)

        self._click_dialog_btn("确认打回")

    def reassign_bug(self, assignee_name: str):
        """[QA/PM] 重新指派缺陷"""
        self.click_header_action("重新指派")
        self.visible(self.DIALOG_TITLE)

        self.click((self.DIALOG_SELECT[0], self.DIALOG_SELECT[1].replace("{label}", "指派人")))
        opt = (By.XPATH,
               f"//li[contains(@class,'el-select-dropdown__item')]//span[contains(text(), '{assignee_name}')]")
        wait_for_first_displayed(self.driver, opt).click()

        self._click_dialog_btn("确定")

    # ================= 流转记录断言 =================

    def get_timeline_actions(self) -> list[str]:
        """获取流转记录中所有的操作动作名称（如：创建、指派、修复）"""
        elements = self.driver.find_elements(*self.TIMELINE_ITEMS)
        actions = []
        for el in elements:
            tag_el = el.find_element(*self.TIMELINE_ITEM_TAG)
            actions.append(tag_el.text.strip())
        return actions