import allure
import pytest
from selenium.webdriver.common.by import By


@allure.feature("UI 自动化")
@allure.story("全局消息通知中心")
class TestNoticeCenterUI:

    @pytest.fixture
    def notice_page(self, driver, env):
        """初始化消息通知组件 POM"""
        from pages.components.notice_center import NoticeCenterComponent
        return NoticeCenterComponent(driver, env["web_base_url"])

    @allure.title("验证未读角标与一键已读交互")
    def test_mark_all_read(self, notice_page, login):
        # 1. 注入 PM 账号 Token 并进入主页
        pm_token = login("pm01")["token"]
        notice_page.driver.execute_script(f"window.localStorage.setItem('litetrack_token', '{pm_token}')")
        notice_page.open_path("/dashboard")

        with allure.step("1. 检查铃铛角标"):
            unread_count = notice_page.get_unread_count()
            # 记录一下初始状态，方便排查日志
            allure.attach(f"初始未读数为: {unread_count}", name="初始状态", attachment_type=allure.attachment_type.TEXT)

            # 如果当前没有未读消息，打开面板刷新一下或者造一条数据
            if unread_count == 0:
                # 这里可以加入造数逻辑，或者直接跳过
                pytest.skip("当前账号没有未读消息，跳过一键已读测试")

        with allure.step("2. 打开面板并点击一键已读"):
            notice_page.open_panel()
            notice_page.click_mark_all_read()

            # 等待 Element Plus 的全局提示 "已全部标为已读" 出现
            notice_page.visible((By.CSS_SELECTOR, ".el-message__content"))

        with allure.step("3. 验证角标消失"):
            # 使用 POM 中更优雅的方式等待角标消失
            import time
            time.sleep(0.5)  # Element Plus 角标缩放的 CSS 动画时间
            assert notice_page.get_unread_count() == 0, "一键已读后，未读角标应当消失"

    @allure.title("验证单条消息删除与悬浮按钮交互")
    def test_delete_message(self, notice_page, login):
        # 1. 注入 QA 账号 Token 并进入主页
        qa_token = login("qa01")["token"]
        notice_page.driver.execute_script(f"window.localStorage.setItem('litetrack_token', '{qa_token}')")
        notice_page.open_path("/dashboard")

        with allure.step("打开消息面板"):
            notice_page.open_panel()
            count_before = notice_page.get_message_count()

            if count_before == 0:
                pytest.skip("当前账号没有任何消息，跳过单条删除测试")

        with allure.step("获取第一条消息的标题"):
            # 兼容性获取：如果 POM 里没封装，可以直接通过组件里的定位器找
            first_msg_el = notice_page.driver.find_elements(*notice_page.MSG_ITEMS)[0]
            title = first_msg_el.find_element(By.CSS_SELECTOR, ".msg-title").text

        with allure.step(f"执行删除消息：{title}"):
            # 调用 POM 中的删除方法（内部会使用 ActionChains 模拟鼠标悬浮）
            notice_page.delete_message(title)

            # 等待删除成功的全局提示
            notice_page.visible((By.CSS_SELECTOR, ".el-message__content"))

        with allure.step("验证消息数量减少"):
            # 因为 DOM 更新可能有微小延迟，稍微等个 0.3 秒
            import time
            time.sleep(0.3)
            assert notice_page.get_message_count() == count_before - 1, "消息数量未按预期减少 1 条"