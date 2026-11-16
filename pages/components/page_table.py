"""通用表格组件 POM。

源码是 src/components/PageTable.vue。
用于处理所有复用该组件的页面中的分页操作、空状态断言以及行选择。
"""

from __future__ import annotations

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from pages.base_page import BasePage


class PageTableComponent(BasePage):
    # ================= 元素定位器 =================
    # 分页器根节点
    PAGINATION = (By.CSS_SELECTOR, ".page-table__pagination .el-pagination")
    # 分页器上的总条数文本（如：共 100 条）
    TOTAL_TEXT = (By.CSS_SELECTOR, ".el-pagination__total")

    # 下一页按钮
    BTN_NEXT_PAGE = (By.CSS_SELECTOR, ".el-pagination button.btn-next")
    # 上一页按钮
    BTN_PREV_PAGE = (By.CSS_SELECTOR, ".el-pagination button.btn-prev")

    # 表格的 DOM 结构
    TABLE = (By.CSS_SELECTOR, ".el-table")
    # 表头
    TABLE_HEADERS = (By.CSS_SELECTOR, ".el-table__header-wrapper th .cell")
    # 数据行
    TABLE_ROWS = (By.CSS_SELECTOR, ".el-table__body-wrapper tr")
    # 空状态提示
    EMPTY_TEXT = (By.CSS_SELECTOR, ".el-table__empty-text")

    # ================= 页面动作与断言 =================

    def get_total_count(self) -> int:
        """提取分页器上的总条数（例如从 '共 42 条' 中提取 42）"""
        text = self.visible(self.TOTAL_TEXT).text
        import re
        match = re.search(r"\d+", text)
        return int(match.group()) if match else 0

    def get_current_page(self) -> int:
        """获取当前处于第几页（通过 active 的页码按钮）"""
        active_page = self.visible((By.CSS_SELECTOR, ".el-pager li.is-active"))
        return int(active_page.text.strip())

    def click_next_page(self) -> None:
        """点击下一页（如果按钮可用的话）"""
        btn = self.visible(self.BTN_NEXT_PAGE)
        if btn.is_enabled():
            btn.click()
            # 可以加一点等待，等表格重新渲染
            import time
            time.sleep(0.5)
        else:
            raise ValueError("下一页按钮不可点击（可能已经是最后一页）")

    def click_prev_page(self) -> None:
        """点击上一页"""
        btn = self.visible(self.BTN_PREV_PAGE)
        if btn.is_enabled():
            btn.click()
            import time
            time.sleep(0.5)
        else:
            raise ValueError("上一页按钮不可点击（可能已经是第一页）")

    def get_empty_text(self) -> str:
        """获取空数据时的提示文本"""
        return self.visible(self.EMPTY_TEXT).text.strip()

    def get_table_headers(self) -> list[str]:
        """获取当前表格的所有列头文本，用于验证列是否根据权限正确渲染"""
        elements = self.driver.find_elements(*self.TABLE_HEADERS)
        return [el.text.strip() for el in elements if el.text.strip()]

    def get_row_by_text(self, text: str) -> WebElement:
        """根据行内的某个文本（如用户名、项目名）定位到整行 <tr> 元素"""
        locator = (By.XPATH, f"//tr[.//td[contains(normalize-space(.), '{text}')]]")
        return self.visible(locator)

    def get_column_text(self, row_text: str, col_index: int) -> str:
        """
        获取指定行、指定列（从 1 开始算）的文本。
        可以用于验证列的数据。
        """
        row = self.get_row_by_text(row_text)
        # 获取该行下的所有 td
        tds = row.find_elements(By.TAG_NAME, "td")
        if 0 < col_index <= len(tds):
            return tds[col_index - 1].text.strip()
        return ""