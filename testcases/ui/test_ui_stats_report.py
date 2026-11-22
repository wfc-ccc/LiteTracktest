"""数据统计看板 UI 用例。

两个身份各一条：ADMIN 看全局视角，DEV 看「我的」个人视角（数据隔离的正反向断言）。
ECharts 画在 Canvas 里读不到图内数据，所以只断言卡片 label/数值 + 图表卡片标题。

账号查找、登录跳转校验、失败诊断、标题等待与归一，全部在页面对象里：
    login_page.login_as(env, "admin")        → pages/login_page.py
    stats_page.check_titles(...)             → pages/stats_page.py
    stats_page.check_cards(...)              → pages/stats_page.py
这里只留业务断言：标题期望列表、反向隔离、D 空状态对照。

标题文案对齐 src/views/stats/Stats.vue 的三个 computed：
    bugStatusChartTitle  ADMIN「缺陷状态分布」   / DEV·QA「我的缺陷状态分布」
    memberChartTitle     ADMIN「成员任务完成情况」/ DEV·QA「我的任务完成情况」
    bugTrendChartTitle   ADMIN「近 7 天缺陷趋势」 / DEV·QA「我近 7 天缺陷趋势」
    第 4 张写死「任务优先级分布」
"""
from __future__ import annotations

import allure
import pytest

pytestmark = pytest.mark.ui

# 期望标题（不带空格；页面对象会先 norm 再比，所以「近 7 天」也能对上）
ADMIN_TITLES = ["缺陷状态分布", "成员任务完成情况", "近7天缺陷趋势", "任务优先级分布"]
DEV_TITLES = ["我的缺陷状态分布", "我的任务完成情况", "我近7天缺陷趋势", "任务优先级分布"]

# statCards 顺序：前两张数值卡、后两张百分比卡
CARD_LABELS = ["任务总数", "缺陷总数", "任务完成率", "缺陷关闭率"]
PERCENT_CARDS = ["任务完成率", "缺陷关闭率"]


@allure.feature("UI 自动化")
@allure.story("数据统计看板")
class TestStatsReportUI:

    @pytest.fixture
    def stats_page(self, driver, env):
        from pages.stats_page import StatsPage
        return StatsPage(driver, env["web_base_url"])

    # login_page 由 conftest 提供，这里不用再定义一遍
    @allure.title("ADMIN 视图：验证全量统计卡片与图表标题")
    def test_stats_admin_view(self, env, stats_page, login_page):
        with allure.step("ADMIN 登录并打开统计报表"):
            login_page.login_as(env, "admin")
            stats_page.open()

        with allure.step("验证图表标题（全局视角，逐个精确比对）"):
            titles = stats_page.check_titles(ADMIN_TITLES, "ADMIN")

        with allure.step("ADMIN 不应出现个人视角的标题"):
            joined = stats_page.norm("".join(titles))
            assert "我的" not in joined, f"ADMIN 视图出现了个人视角标题：{titles!r}"

        with allure.step("验证卡片 label 顺序、数值已渲染、数值形态"):
            stats_page.check_cards(CARD_LABELS, PERCENT_CARDS)

        with allure.step("打印页面事实，方便日后核对文案"):
            stats_page.debug_dump()

    @allure.title("DEV 视图：验证『我的』专属图表标题与数据隔离")
    def test_stats_dev_view(self, env, stats_page, login_page):
        with allure.step("DEV 登录并打开统计报表"):
            login_page.login_as(env, "dev01")
            stats_page.open()

        with allure.step("验证图表标题（个人视角，逐个精确比对）"):
            titles = stats_page.check_titles(DEV_TITLES, "DEV")

        with allure.step("确认没有出现全局视角的字样"):
            joined = stats_page.norm("".join(titles))
            for bad in ("全体成员", "所有成员", "成员任务完成情况"):
                assert stats_page.norm(bad) not in joined, \
                    f"DEV 视图里出现了全局视角标题「{bad}」：{titles!r}"

        with allure.step("DEV 也能看到同样的 4 张统计卡片（statCards 不按角色区分）"):
            stats_page.check_cards(CARD_LABELS, PERCENT_CARDS)

        with allure.step("标题与空状态对照（标题是 computed，不受有无数据影响）"):
            for i, title in enumerate(titles):
                print(f"[STATS] 第 {i + 1} 张图 {title!r}，空状态={stats_page.is_chart_empty(i)}")
