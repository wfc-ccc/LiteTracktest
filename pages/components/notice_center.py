from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from pages.base_page import BasePage


class NoticeCenterComponent(BasePage):
    """消息通知中心铃铛组件"""
    # 定位器
    BELL_ICON = (By.CSS_SELECTOR, ".notice-bell")
    UNREAD_BADGE = (By.CSS_SELECTOR, ".notice-badge")
    MARK_ALL_READ_BTN = (By.CSS_SELECTOR, ".mark-all-read")
    MSG_ITEMS = (By.CSS_SELECTOR, ".notice-message-item")
    MSG_DELETE_BTN = (By.CSS_SELECTOR, ".msg-delete")

    def __init__(self, driver, base_url):
        super().__init__(driver, base_url)
        self.action = ActionChains(driver)

    def open_panel(self):
        """点击铃铛打开消息面板"""
        self.click(self.BELL_ICON)

    def get_unread_count(self):
        """获取未读角标数字，无角标返回0"""
        try:
            el = self.find(self.UNREAD_BADGE, timeout=1)
            return int(el.text.strip())
        except Exception:
            return 0

    def click_mark_all_read(self):
        """点击一键已读"""
        self.click(self.MARK_ALL_READ_BTN)

    def get_message_count(self):
        """获取当前面板消息条数"""
        items = self.find_elements(self.MSG_ITEMS)
        return len(items)

    def delete_message(self, title: str):
        """悬浮到指定标题消息，点击删除"""
        items = self.find_elements(self.MSG_ITEMS)
        for item in items:
            title_ele = item.find_element(By.CSS_SELECTOR, ".msg-title")
            if title_ele.text.strip() == title.strip():
                self.action.move_to_element(item).perform()
                del_btn = item.find_element(*self.MSG_DELETE_BTN)
                del_btn.click()
                return
        raise AssertionError(f"未找到标题为【{title}】的消息")
