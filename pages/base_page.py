"""页面对象基类：只通过显式等待操作元素。"""

from __future__ import annotations

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from utils.waits import wait_for_element_clickable, wait_for_element_visible


class BasePage:
    def __init__(self, driver: WebDriver, base_url: str):
        self.driver = driver
        self.base_url = base_url.rstrip("/")

    def open_path(self, path: str) -> None:
        self.driver.get(f"{self.base_url}{path}")

    def visible(self, locator: tuple, timeout: float = 10) -> WebElement:
        return wait_for_element_visible(self.driver, locator, timeout)

    def clickable(self, locator: tuple, timeout: float = 10) -> WebElement:
        return wait_for_element_clickable(self.driver, locator, timeout)

    def type_text(self, locator: tuple, text: str, timeout: float = 10) -> None:
        element = self.clickable(locator, timeout)
        element.clear()
        element.send_keys(text)

    def click(self, locator: tuple, timeout: float = 10) -> None:
        self.clickable(locator, timeout).click()
