"""Element Plus 表格的通用读取工具。

为什么要单独抽：项目列表第一列是 ID、用户列表状态在第 5 列，直接写 td[0]/td[5]
在列顺序一变就静默读错值（上一轮扫出 ['324','226'] 当项目名就是这么来的）。
这里统一按表头文字定位列，再按 td 上的 `el-table_N_column_M` 精确取单元格。
"""
from __future__ import annotations

import re

from selenium.webdriver.common.by import By

# td/th 的 class 形如 el-table_1_column_3，用它精确定位第 3 列
COLUMN_CLASS_RE = re.compile(r"el-table_\d+_column_(\d+)")


def headers(driver) -> list:
    """表头文本列表（空白已归一）。"""
    return [" ".join((th.text or "").split())
            for th in driver.find_elements(By.CSS_SELECTOR, ".el-table__header th")]


def column_index(driver, keywords, fallback: int | None = None) -> int | None:
    """按表头文本找列序号（1-based），找不到返回 fallback。"""
    for i, th in enumerate(driver.find_elements(By.CSS_SELECTOR, ".el-table__header th"), start=1):
        text = " ".join((th.text or "").split())
        if any(k in text for k in keywords):
            return i
    return fallback


def cell_element(tr, idx: int):
    """按列序号取单元格元素（td class 带列号），失败退化成按下标取。"""
    tds = tr.find_elements(By.CSS_SELECTOR, "td")
    for td in tds:
        m = COLUMN_CLASS_RE.search(td.get_attribute("class") or "")
        if m and int(m.group(1)) == idx:
            return td
    if 0 < idx <= len(tds):
        return tds[idx - 1]
    return None


def cell_text(tr, idx: int) -> str:
    el = cell_element(tr, idx)
    return " ".join((el.text or "").split()) if el else ""


def body_rows(driver) -> list:
    """表体数据行（过滤掉展开行/空行）。"""
    return [tr for tr in driver.find_elements(By.CSS_SELECTOR, ".el-table__body tr")
            if tr.find_elements(By.CSS_SELECTOR, "td")]


def column_values(driver, keywords, fallback: int = 2, exclude=()) -> list:
    """取某一列的所有值（按表头关键词定位列），用于项目名/用户名这类列表扫描。"""
    idx = column_index(driver, keywords, fallback)
    values = []
    for tr in body_rows(driver):
        text = cell_text(tr, idx)
        if text and text not in exclude and text not in values:
            values.append(text)
    return values
