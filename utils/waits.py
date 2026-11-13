"""Selenium 4 显式等待。用例与页面对象禁止使用 time.sleep。"""

from __future__ import annotations

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

DEFAULT_TIMEOUT = 10


def wait_for_element_visible(driver: WebDriver, locator: tuple, timeout: float = DEFAULT_TIMEOUT) -> WebElement:
    """等待元素出现在 DOM 中且可见。locator 为 (By, value)。"""
    return WebDriverWait(driver, timeout).until(EC.visibility_of_element_located(locator))


def wait_for_element_clickable(driver: WebDriver, locator: tuple, timeout: float = DEFAULT_TIMEOUT) -> WebElement:
    """等待元素可见且可点击。"""
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable(locator))


def wait_for_url_contains(driver: WebDriver, fragment: str, timeout: float = DEFAULT_TIMEOUT) -> bool:
    """等待地址栏包含指定片段，用于登录后跳转到 /dashboard。"""
    return WebDriverWait(driver, timeout).until(EC.url_contains(fragment))


def wait_for_first_displayed(driver: WebDriver, locator: tuple, timeout: float = DEFAULT_TIMEOUT) -> WebElement:
    """等待匹配 locator 的元素中第一个「可见」的那个。

    Element Plus 的下拉面板常驻 DOM，关闭时只是 ``display: none``，
    EC.visibility_of_element_located 只认第一个匹配项，会一直等隐藏的那个而超时。
    """
    def _first_displayed(driver: WebDriver) -> WebElement | bool:
        for element in driver.find_elements(*locator):
            if element.is_displayed():
                return element
        return False

    return WebDriverWait(driver, timeout).until(_first_displayed)
