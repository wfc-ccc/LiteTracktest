"""工作台首页 POM。

源码是 src/views/Dashboard.vue。
涉及多角色视图切换、项目概览面板、任务/缺陷列表，以及审核未通过的悬浮气泡。
"""

from __future__ import annotations

from selenium.webdriver.common.by import By

from pages.base_page import BasePage
from utils.waits import wait_for_element_visible


class DashboardPage(BasePage):
    # ================= 元素定位器 =================

    # 未读动态提示 (el-alert)
    UNREAD_ALERT = (By.CSS_SELECTOR, ".dashboard__hint")
    UNREAD_TEXT = (By.CSS_SELECTOR, ".dashboard__hint .el-alert__title")

    # 统计卡片 (根据 label 匹配)
    STAT_CARD = (By.XPATH, "//div[contains(@class, 'stat-card')][.//div[text()='{label}']]")
    STAT_VALUE = (By.CSS_SELECTOR, ".stat-card__value")

    # PM / ADMIN 专属：项目概览面板
    PM_OVERVIEW_CARD = (By.CSS_SELECTOR, ".pm-overview")
    PM_OVERVIEW_TITLE = (By.CSS_SELECTOR, ".pm-overview .card-header span")
    PM_PROJECT_CARD = (By.CSS_SELECTOR, ".pm-card")
    PM_PROJECT_TITLE = (By.CSS_SELECTOR, ".pm-card__title")

    # 底部表格
    # 通过所在的列来区分是任务表格还是缺陷表格
    TASK_TABLE_TITLE = (By.XPATH,
                        "//div[contains(@class, 'el-row dashboard__row')]//div[contains(@class, 'el-col')][1]//div[contains(@class, 'card-header')]//span")
    BUG_TABLE_TITLE = (By.XPATH,
                       "//div[contains(@class, 'el-row dashboard__row')]//div[contains(@class, 'el-col')][2]//div[contains(@class, 'card-header')]//span")

    # 表格行 (假设我们通过任务/缺陷标题来定位行)
    TASK_ROW = (By.XPATH,
                "//div[contains(@class, 'el-col')][1]//tr[.//span[contains(@class,'task-cell__title') and contains(text(), '{title}')]]")
    BUG_ROW = (By.XPATH, "//div[contains(@class, 'el-col')][2]//tr[.//td[contains(text(), '{title}')]]")

    # 审核未通过标签及气泡
    AUDIT_REJECT_FLAG = (By.CSS_SELECTOR, ".task-audit-flag")
    AUDIT_REJECT_POPPER = (By.CSS_SELECTOR, ".audit-reject-popper")
    AUDIT_REJECT_REASON = (By.CSS_SELECTOR, ".audit-reject-popper__reason")

    # ================= 页面动作 =================

    def open(self) -> None:
        """打开工作台"""
        self.open_path("/dashboard")
        # 等待页面核心元素（统计卡片）加载完成
        self.visible((By.CSS_SELECTOR, ".stat-card"))

    # ---------- 数据获取 ----------

    def get_stat_value(self, label: str) -> str:
        """
        获取统计卡片的值。
        :param label: 卡片的标签（如 '待办任务', '我的待办任务'）
        """
        card_loc = (self.STAT_CARD[0], self.STAT_CARD[1].replace("{label}", label))
        card = self.visible(card_loc)
        return card.find_element(*self.STAT_VALUE).text.strip()

    def get_unread_hint(self) -> str:
        """获取未读动态提示文本（如果没有未读，调用此方法会超时）"""
        return self.visible(self.UNREAD_TEXT).text.strip()

    def get_pm_overview_title(self) -> str:
        """获取项目概览面板的标题"""
        return self.visible(self.PM_OVERVIEW_TITLE).text.strip()

    def get_table_titles(self) -> tuple[str, str]:
        """获取任务表格和缺陷表格的标题"""
        task_title = self.visible(self.TASK_TABLE_TITLE).text.strip()
        bug_title = self.visible(self.BUG_TABLE_TITLE).text.strip()
        return task_title, bug_title

    # ---------- 列表交互 ----------

    def click_task_row(self, title: str) -> None:
        """点击任务列表中的某一行，跳转到任务看板"""
        row_loc = (self.TASK_ROW[0], self.TASK_ROW[1].replace("{title}", title))
        self.click(row_loc)

    def click_bug_row(self, title: str) -> None:
        """点击缺陷列表中的某一行，跳转到缺陷详情"""
        row_loc = (self.BUG_ROW[0], self.BUG_ROW[1].replace("{title}", title))
        self.click(row_loc)

    # ---------- 气泡交互 ----------

    def click_audit_reject_flag(self) -> None:
        """点击任务列表中的『审核未通过』标签，弹出气泡"""
        self.click(self.AUDIT_REJECT_FLAG)

    def get_audit_reject_reason(self) -> str:
        """获取悬浮气泡中的审核未通过原因"""
        self.visible(self.AUDIT_REJECT_POPPER)
        return self.visible(self.AUDIT_REJECT_REASON).text.strip()