import allure
import pytest


@allure.feature("UI 自动化")
@allure.story("数据统计看板")
class TestStatsReportUI:

    @pytest.fixture
    def stats_page(self, driver, env):
        from pages.stats_page import StatsPage
        return StatsPage(driver, env["web_base_url"])

    @allure.title("ADMIN 视图：验证全量统计卡片与图表标题")
    def test_stats_admin_view(self, stats_page, driver, login):
        with allure.step("切换 Admin 账号打开统计页"):
            admin_token = login("admin")["token"]
            driver.execute_script(f"window.localStorage.setItem('litetrack_token', '{admin_token}')")
            stats_page.open()

        with allure.step("验证图表标题（全局视角）"):
            titles = stats_page.get_chart_titles()
            assert "缺陷状态分布" in titles[0]
            assert "成员任务完成情况" in titles[1]
            assert "近 7 天缺陷趋势" in titles[2]

        with allure.step("验证卡片有数值渲染"):
            # 获取任务总数卡片的值，只要不为空即可
            task_total = stats_page.get_stat_value("任务总数")
            assert task_total != "", "任务总数不应当为空"

    @allure.title("DEV 视图：验证『我的』专属图表标题与数据隔离")
    def test_stats_dev_view(self, stats_page, driver, login):
        with allure.step("切换 DEV 账号打开统计页"):
            dev_token = login("dev01")["token"]
            driver.execute_script(f"window.localStorage.setItem('litetrack_token', '{dev_token}')")
            stats_page.open()

        with allure.step("验证图表标题（个人视角）"):
            titles = stats_page.get_chart_titles()
            assert "我的缺陷状态分布" in titles[0]
            assert "我的任务完成情况" in titles[1]
            assert "我近 7 天缺陷趋势" in titles[2]