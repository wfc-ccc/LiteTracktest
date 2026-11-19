import allure
import pytest
from selenium.webdriver.common.by import By


@allure.feature("UI 自动化")
@allure.story("全局交互组件")
class TestGlobalComponentsUI:

    def test_notice_center_operations(self, driver, env, login):
        from pages.components.notice_center import NoticeCenterComponent
        notice = NoticeCenterComponent(driver, env["web_base_url"])

        with allure.step("登录并打开通知面板"):
            pm_token = login("pm01")["token"]
            driver.get(env["web_base_url"])
            driver.execute_script(f"window.localStorage.setItem('litetrack_token', '{pm_token}')")
            driver.get(f"{env['web_base_url']}/dashboard")

            notice.open_panel()

        with allure.step("验证一键已读功能"):
            initial_count = notice.get_unread_count()
            if initial_count > 0:
                notice.click_mark_all_read()
                import time;
                time.sleep(0.5)
                assert notice.get_unread_count() == 0

    def test_ai_assistant_chat(self, driver, env, login):
        from pages.components.ai_assistant import AiAssistantComponent
        ai = AiAssistantComponent(driver, env["web_base_url"])

        with allure.step("打开 AI 助手并发送问题"):
            pm_token = login("pm01")["token"]
            driver.execute_script(f"window.localStorage.setItem('litetrack_token', '{pm_token}')")
            driver.get(f"{env['web_base_url']}/dashboard")

            ai.open_panel()
            ai.send_message("请简单介绍一下你自己")

        with allure.step("等待流式回复完成"):
            reply = ai.wait_for_ai_reply(timeout=30)
            assert len(reply) > 0, "AI 未返回任何内容"