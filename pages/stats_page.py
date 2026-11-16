"""统计报表页 POM。

源码是 src/views/stats/Stats.vue。
由于 ECharts 渲染在 Canvas 中无法直接通过 DOM 文本断言，
主要验证：统计卡片数值、图表标题，以及无数据时的空状态。
"""

from __future__ import annotations

from selenium.webdriver.common.by import By

from pages.base_page import BasePage
from utils.waits import wait_for_first_displayed, wait_for_element_visible


class StatsPage(BasePage):
    # ================= 元素定位器 =================
    PAGE_TITLE = (By.CSS_SELECTOR, ".stats-header__title")

    # 顶部项目选择器
    PROJECT_SELECT = (By.CSS_SELECTOR, ".stats-header .el-select")
    PROJECT_INPUT = (By.CSS_SELECTOR, ".stats-header .el-select input")
    # 下拉面板（挂在 body 上）
    PROJECT_OPTION = (By.XPATH, "//li[contains(@class,'el-select-dropdown__item')]//span[text()='{name}']")

    # 统计卡片 (根据 label 找到整个卡片，再取内部数值)
    # 假设要找 "任务总数" 的卡片
    STAT_CARD = (By.XPATH, "//div[contains(@class, 'stat-card')][.//div[text()='{label}']]")
    STAT_VALUE = (By.CSS_SELECTOR, ".stat-card__value")
    STAT_PROGRESS = (By.CSS_SELECTOR, ".stat-card__progress .el-progress__text")

    # 图表卡片（按顺序：0-缺陷状态, 1-成员任务, 2-缺陷趋势, 3-优先级）
    CHART_HEADERS = (By.CSS_SELECTOR, ".chart-card .el-card__header")
    CHART_EMPTY = (By.CSS_SELECTOR, ".chart-box__empty .el-empty__description")

    # ================= 页面动作 =================

    def open(self) -> None:
        """打开统计报表页并等待加载"""
        self.open_path("/stats")
        self.visible(self.PAGE_TITLE)

    def select_project(self, project_name: str) -> None:
        """切换顶部项目筛选下拉框"""
        self.click(self.PROJECT_SELECT)

        # 动态替换下拉选项的 XPath
        option_loc = (self.PROJECT_OPTION[0], self.PROJECT_OPTION[1].replace("{name}", project_name))
        wait_for_first_displayed(self.driver, option_loc).click()

        # 等待数据重新加载（根据 v-loading，可以等待遮罩层消失，这里简单处理等待页面标题依然可见）
        self.visible(self.PAGE_TITLE)

    # ================= 断言辅助 =================

    def get_stat_value(self, label: str) -> str:
        """
        获取指定统计卡片的值。
        例如：get_stat_value("任务总数") -> "12"
        如果是百分比卡片，例如：get_stat_value("任务完成率") -> "50%"
        """
        card_loc = (self.STAT_CARD[0], self.STAT_CARD[1].replace("{label}", label))
        card_el = self.visible(card_loc)

        # 尝试获取普通数值
        try:
            return card_el.find_element(*self.STAT_VALUE).text.strip()
        except Exception:
            pass

        # 尝试获取进度条文字 (Element Plus 进度条文字通常在 .el-progress__text 中)
        try:
            return card_el.find_element(*self.STAT_PROGRESS).text.strip()
        except Exception:
            return ""

    def get_chart_titles(self) -> list[str]:
        """获取 4 个图表卡片的标题列表"""
        elements = self.driver.find_elements(*self.CHART_HEADERS)
        return [el.text.strip() for el in elements]

    def is_chart_empty(self, index: int) -> bool:
        """
        判断第 N 个图表是否显示为“暂无数据”状态。
        注意：如果图表有数据，此处可能返回 False 或抛出异常；因此尝试寻找。
        """
        try:
            headers = self.driver.find_elements(*self.CHART_HEADERS)
            if index < len(headers):
                # 在该卡片的父容器内查找空状态提示
                parent = headers[index].find_element(By.XPATH, "./ancestor::div[contains(@class,'chart-card')]")
                empty_el = parent.find_element(*self.CHART_EMPTY)
                return empty_el.is_displayed() and "暂无数据" in empty_el.text
        except Exception:
            pass
        return False