import allure


@allure.feature("API - 工作台与通知")
class TestNotificationApi:

    def test_notification_flow(self, pm_client):
        from api.notification_api import NotificationApi
        notif_api = NotificationApi(pm_client, base_url="")

        with allure.step("1. 获取未读消息数"):
            # 假设之前有造数触发通知
            unread_data = notif_api.get_unread_updates()
            assert "totalCount" in unread_data or isinstance(unread_data, dict)

        with allure.step("2. 一键已读"):
            notif_api.mark_all_as_read()
            # 再次获取，未读数应该为 0
            assert notif_api.get_unread_updates().get("totalCount") == 0

        with allure.step("3. 清空消息"):
            notif_api.clear_all_messages()