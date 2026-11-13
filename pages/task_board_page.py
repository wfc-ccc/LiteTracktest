"""任务看板 POM。

源码是 src/views/task/TaskBoard.vue，路由 /projects/:id/board。
页面没有 data-test。筛选区用 placeholder，按钮用文案，标题用 .task-title-link。
"""

from __future__ import annotations

from selenium.webdriver.common.by import By

from pages.base_page import BasePage
from utils.waits import wait_for_first_displayed


class TaskBoardPage(BasePage):
    HEADER_NAME = (By.CSS_SELECTOR, ".board-header__name")
    KEYWORD_INPUT = (By.CSS_SELECTOR, ".filter-bar input[placeholder='请输入标题关键字']")
    STATUS_SELECT = (By.CSS_SELECTOR, ".filter-bar .el-select")
    SEARCH_BUTTON = (By.XPATH, "//div[contains(@class,'filter-bar')]//button[contains(., '查询')]")
    RESET_BUTTON = (By.XPATH, "//div[contains(@class,'filter-bar')]//button[contains(., '重置')]")
    CREATE_BUTTON = (By.XPATH, "//div[contains(@class,'filter-bar')]//button[contains(., '新建任务')]")
    REFRESH_BUTTON = (By.XPATH, "//div[contains(@class,'filter-bar')]//button[contains(., '刷新')]")
    TASK_TITLE = (By.CSS_SELECTOR, ".el-table .task-title-link")
    DETAIL_BUTTON = (By.XPATH, "//div[contains(@class,'el-table')]//button[contains(., '详情')]")
    CREATE_DIALOG_TITLE = (By.XPATH, "//div[contains(@class,'el-dialog')]//span[contains(@class,'el-dialog__title') and contains(., '新建任务')]")

    # 新建任务弹窗
    CREATE_TITLE_INPUT = (By.CSS_SELECTOR, ".el-dialog input[placeholder='请输入任务标题']")
    CREATE_ASSIGNEE_SELECT = (
        By.XPATH,
        "//div[contains(@class,'el-dialog')]//div[contains(@class,'el-form-item')]"
        "[.//label[contains(., '指派给')]]//div[contains(@class,'el-select')]",
    )
    CREATE_CONFIRM_BUTTON = (By.XPATH, "//div[contains(@class,'el-dialog__footer')]//button[contains(., '确定')]")
    # 下拉面板挂在 body 上，关闭的那几个只是 display:none，所以用「第一个可见项」
    ASSIGNEE_OPTION = (By.XPATH, "//li[contains(@class,'el-select-dropdown__item')]")

    # 任务详情抽屉
    DRAWER_TITLE = (By.XPATH, "//*[contains(@class,'el-drawer__title')]")
    ACCEPT_BUTTON = (By.XPATH, "//div[contains(@class,'el-drawer')]//button[contains(., '接受任务')]")

    def open(self, project_id: int) -> None:
        self.open_path(f"/projects/{project_id}/board")
        self.visible(self.HEADER_NAME)

    def header_name(self) -> str:
        return self.visible(self.HEADER_NAME).text.strip()

    def search(self, keyword: str) -> None:
        self.type_text(self.KEYWORD_INPUT, keyword)
        self.click(self.SEARCH_BUTTON)

    def open_create_dialog(self) -> None:
        self.click(self.CREATE_BUTTON)
        self.visible(self.CREATE_DIALOG_TITLE)

    def first_task_title(self) -> str:
        return self.visible(self.TASK_TITLE).text.strip()

    # ---------- 新建任务 ----------
    def fill_create_form(self, title: str) -> None:
        """填标题并选一个负责人。指派下拉只列 DEV / QA，取第一个可见项即可。"""
        self.type_text(self.CREATE_TITLE_INPUT, title)
        self.click(self.CREATE_ASSIGNEE_SELECT)
        wait_for_first_displayed(self.driver, self.ASSIGNEE_OPTION).click()

    def submit_create(self) -> None:
        self.click(self.CREATE_CONFIRM_BUTTON)

    # ---------- 列表行 ----------
    def _row_title(self, title: str) -> tuple:
        return (By.XPATH, f"//span[contains(@class,'task-title-link') and normalize-space(.)='{title}']")

    def wait_row(self, title: str, timeout: float = 10):
        """等待表格里出现指定标题，返回该标题元素。"""
        return self.visible(self._row_title(title), timeout)

    def row_status(self, title: str) -> str:
        """取该任务所在行的状态标签文案。状态是表格第 2 列。"""
        locator = (
            By.XPATH,
            f"//tr[.//span[contains(@class,'task-title-link') and normalize-space(.)='{title}']]"
            f"/td[2]//span[contains(@class,'el-tag')]",
        )
        return self.visible(locator).text.strip()

    # ---------- 详情抽屉 ----------
    def open_detail(self, title: str) -> None:
        self.click(self._row_title(title))
        self.visible(self.DRAWER_TITLE)

    def accept_task(self) -> None:
        self.click(self.ACCEPT_BUTTON)

    # ---------- 全局提示 ----------
    def wait_message(self, text: str, timeout: float = 10) -> None:
        """等待 Element Plus 的全局提示出现并命中关键文案。"""
        self.visible(
            (By.XPATH, f"//p[contains(@class,'el-message__content') and contains(., '{text}')]"),
            timeout,
        )
