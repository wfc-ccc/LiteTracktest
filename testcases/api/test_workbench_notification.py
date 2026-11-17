import allure
import pytest
from api.notification_api import NotificationApi

class TestNotificationApi:

    @pytest.fixture
    def notif_api(self, pm_client, env):
        return NotificationApi(pm_client, env["api_base_url"])

    @allure.story("站内通知-消息主流程")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("工作台未读统计 -> 查询消息列表 -> 标记单条已读 -> 全部标记已读 -> 清空消息")
    def test_notification_flow(self, notif_api):
        with allure.step("1. 获取工作台未读消息统计"):
            unread_data = notif_api.unread_updates()
            allure.attach(str(unread_data), "未读统计结果", allure.attachment_type.TEXT)

        with allure.step("2. 获取最近消息列表"):
            msg_list = notif_api.list_recent()
            allure.attach(str(msg_list), "最近消息列表", allure.attachment_type.TEXT)

        if msg_list:
            first_id = msg_list[0]["id"]
            with allure.step(f"3. 标记单条消息 {first_id} 为已读"):
                notif_api.mark_read(first_id)

        with allure.step("4. 全部标记为已读"):
            notif_api.mark_all_as_read()

        with allure.step("5. 清空全部消息"):
            notif_api.clear_all_messages()
