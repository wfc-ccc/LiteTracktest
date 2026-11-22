"""统计报表页 POM。

源码是 src/views/stats/Stats.vue。
ECharts 画在 Canvas 里，DOM 上读不到图里的数据，所以这层只负责：
统计卡片 label/数值、图表卡片标题、无数据时的空状态。

【本版说明：把用例里的辅助函数收进页面对象】
- `norm()`           文本归一（去全部空白），标题比较统一走这里
- `wait_chart_titles()`  等图表标题就绪并返回 list（原来散在用例里的 _wait_titles）
- `check_titles()`   逐个精确比对标题，不做 `in`（避免「我的X」包含「X」的假阳性）
- `check_cards()`    校验卡片 label 顺序 + 数值已渲染 + 数值形态，返回 {label: value}
用例里只剩业务断言（比如「ADMIN 不该出现我的」）。

【时序要点】`loading = ref(false)` 是初值，fetchAll() 开头才置 true，
所以 open() 先用 wait_loading_cycle() 努力抓到遮罩出现→消失，
再用 wait_stats_stable() 连续 3 次采样一致兜底，避免读到 overview 的初始 0。
"""
from __future__ import annotations

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException

from pages.base_page import BasePage
from utils.waits import (
    wait_for_first_displayed,
    wait_for_element_visible,
    wait_for_element_invisible,
)


def _class_token(cls: str) -> str:
    """XPath 里按「class 整词」匹配，避免 stat-card 命中 stat-card__label。"""
    return f"contains(concat(' ', normalize-space(@class), ' '), ' {cls} ')"


class StatsPage(BasePage):
    # ================= 元素定位器 =================
    PAGE_TITLE = (By.CSS_SELECTOR, ".stats-header__title")

    # 顶部项目选择器
    PROJECT_SELECT = (By.CSS_SELECTOR, ".stats-header .el-select")
    PROJECT_INPUT = (By.CSS_SELECTOR, ".stats-header .el-select input")
    # 下拉面板（挂在 body 上）
    PROJECT_OPTION = (By.XPATH, "//li[contains(@class,'el-select-dropdown__item')]//span[text()='{name}']")

    # 统计卡片：整词匹配 stat-card，label 精确匹配
    STAT_CARD = (By.XPATH, f"//div[{_class_token('stat-card')}][.//div[normalize-space(text())='{{label}}']]")
    STAT_CARD_ANY = (By.CSS_SELECTOR, ".stat-card")
    STAT_LABEL = (By.CSS_SELECTOR, ".stat-card__label")
    STAT_VALUE = (By.CSS_SELECTOR, ".stat-card__value")
    STAT_PROGRESS = (By.CSS_SELECTOR, ".stat-card__progress .el-progress__text")

    # 图表卡片
    CHART_HEADERS = (By.CSS_SELECTOR, ".chart-card .el-card__header")
    CHART_EMPTY = (By.CSS_SELECTOR, ".chart-box__empty .el-empty__description")

    # 通用 loading 遮罩
    LOADING_MASK = (By.CSS_SELECTOR, ".el-loading-mask")

    # ================= 文本归一 =================
    @staticmethod
    def norm(text: str) -> str:
        """去掉所有空白再比较。

        前端标题会写成「近 7 天缺陷趋势」，断言里写「近7天缺陷趋势」，
        直接比较差一个空格就红，统一归一后再比。
        """
        return "".join((text or "").split())

    # ================= 页面动作 =================
    def open(self, timeout: float = 20) -> None:
        """打开统计报表页。

        不硬等 .stats-header__title（万一类名变了会污染所有用例），
        只要是「标题 或 任意一张卡片」出现，就认为页面进来了。
        """
        self.open_path("/stats")

        def _ready(driver):
            for loc in (self.PAGE_TITLE, self.STAT_CARD_ANY):
                try:
                    if driver.find_elements(*loc):
                        return True
                except Exception:
                    continue
            return False

        try:
            WebDriverWait(self.driver, timeout, poll_frequency=0.3,
                          ignored_exceptions=(NoSuchElementException,)).until(_ready)
        except Exception:
            raise AssertionError(
                f"打开统计页后 {timeout}s 内既没有 .stats-header__title 也没有 .stat-card，"
                f"当前 URL={self.driver.current_url}——检查 StatsPage.open 的路径是不是 /stats"
            )
        self.wait_loading_cycle()

    def wait_loading_off(self, timeout: float = 20) -> None:
        """等 v-loading 遮罩撤掉（没有遮罩时立刻返回）。"""
        def _gone(driver):
            masks = driver.find_elements(*self.LOADING_MASK)
            return all(not m.is_displayed() for m in masks)

        try:
            WebDriverWait(self.driver, timeout, poll_frequency=0.3,
                          ignored_exceptions=(NoSuchElementException,)).until(_gone)
        except Exception:
            print(f"[STATS] ⚠️ loading 遮罩 {timeout}s 内没消失，继续往下走")

    def wait_loading_cycle(self, appear_timeout: float = 2, timeout: float = 20) -> None:
        """尽量抓到一次遮罩的「出现 → 消失」。

        `loading` 初值是 ref(false)，fetchAll() 开头才置 true，遮罩可能在页面
        就绪之后才出现。所以只等「消失」会秒过、读到初始 0。这里先努力抓到出现，
        抓不到（接口太快）就直接返回，交给 wait_stats_stable 的多轮采样兜底。
        """
        try:
            WebDriverWait(self.driver, appear_timeout, poll_frequency=0.1).until(
                lambda d: any(m.is_displayed() for m in d.find_elements(*self.LOADING_MASK))
            )
        except Exception:
            return
        self.wait_loading_off(timeout=timeout)

    def select_project(self, project_name: str) -> None:
        """切换顶部项目筛选下拉框"""
        self.click(self.PROJECT_SELECT)
        option_loc = (self.PROJECT_OPTION[0], self.PROJECT_OPTION[1].replace("{name}", project_name))
        wait_for_first_displayed(self.driver, option_loc).click()
        # 下拉收起，再等数据重新渲染
        try:
            wait_for_element_invisible(self.driver, (By.CSS_SELECTOR, ".el-select-dropdown"), 5)
        except Exception:
            pass
        self.wait_loading_cycle()

    # ================= 卡片读取 =================
    def get_stat_value(self, label: str, timeout: float = 10, wait_loading: bool = True) -> str:
        """取指定统计卡片的值。

        例：get_stat_value("任务总数") -> "12"
            get_stat_value("任务完成率") -> "50%"（百分比卡走 el-progress 的文本）
        取不到返回空串（交给 check_cards 断言，报错信息里会带卡片原文）。

        wait_loading=False 用于轮询采样时跳过遮罩等待，避免每次采样都等 5s。
        """
        if wait_loading:
            self.wait_loading_off(timeout=5)

        card_loc = (self.STAT_CARD[0], self.STAT_CARD[1].replace("{label}", label))
        card_el = self.visible(card_loc, timeout=timeout)

        try:
            txt = (card_el.find_element(*self.STAT_VALUE).text or "").strip()
            if txt:
                return txt
        except Exception:
            pass

        try:
            txt = (card_el.find_element(*self.STAT_PROGRESS).text or "").strip()
            if txt:
                return txt
        except Exception:
            pass

        print(f"[STATS] ⚠️ 卡片「{label}」里没找到 .stat-card__value / .el-progress__text，"
              f"卡片原文 = {(card_el.text or '').strip()!r}")
        return ""

    def get_card_labels(self) -> list:
        """所有统计卡片的 label，按页面顺序。"""
        labels = []
        for el in self.driver.find_elements(*self.STAT_CARD_ANY):
            try:
                t = (el.find_element(*self.STAT_LABEL).text or "").strip()
            except Exception:
                continue
            if t:
                labels.append(t)
        return labels

    def _read_all_values(self, labels: list) -> dict:
        """一次采样：{label: value}。采样期间不等遮罩，交给 wait_stats_stable 反复采。"""
        out = {}
        for label in labels:
            try:
                out[label] = self.get_stat_value(label, timeout=2, wait_loading=False)
            except Exception:
                out[label] = "<取不到>"
        return out

    def wait_stats_stable(self, labels: list, stable_rounds: int = 3,
                          timeout: float = 15, poll: float = 0.5) -> dict:
        """等卡片数值稳定：连续 stable_rounds 次采样完全一致，才认为数据已落定。

        为什么不只靠遮罩：`loading = ref(false)` 是初值，fetchAll() 开头才置 true，
        页面刚就绪时遮罩可能还没出现，「等遮罩消失」会秒过、读到 overview 的初始 0。
        也不靠「两次一致」——两次都在 API 返回前采样就都是 0，一样会骗过判定。
        连续 3 次（约 1.5s）既不用 sleep，也给了本地接口足够的返回时间。
        """
        last: dict = {}
        streak = 0

        def _probe(_driver):
            nonlocal last, streak
            cur = self._read_all_values(labels)
            complete = bool(cur) and all(v not in ("", "<取不到>") for v in cur.values())
            if complete and cur == last:
                streak += 1
                if streak >= stable_rounds:
                    return cur
            else:
                streak = 0
            last = cur
            return False

        try:
            return WebDriverWait(self.driver, timeout, poll_frequency=poll).until(_probe)
        except Exception:
            print(f"[STATS] ⚠️ 卡片数值 {timeout}s 内没稳定（连续 {stable_rounds} 次一致才算稳定），"
                  f"最后一次 = {last}")
            return last

    def check_cards(self, expected_labels: list, percent_labels: list = ()) -> dict:
        """校验卡片：label 顺序、数值已渲染、数值形态。

        只校验前 len(expected_labels) 个 label，允许后面再加卡片（加卡不该红用例）。
        数值卡必须纯整数（容忍千分位逗号），百分比卡必须带 % 后缀。
        返回稳定后的 {label: value}，供用例做进一步断言。
        """
        labels = self.get_card_labels()
        print(f"[STATS] 卡片 label：{labels}")
        assert labels[:len(expected_labels)] == list(expected_labels), (
            f"卡片顺序/文案不对：实际 {labels!r}，期望前 {len(expected_labels)} 个是 "
            f"{list(expected_labels)!r}"
        )

        values = self.wait_stats_stable(list(expected_labels))
        print(f"[STATS] 卡片数值：{values}")

        for label in expected_labels:
            raw = str(values.get(label, "")).strip()
            assert raw, (
                f"卡片「{label}」取不到值——跑 print(stats_page.debug_dump()) 对照真实 DOM"
            )
            if label in percent_labels:
                assert raw.endswith("%"), f"「{label}」是进度卡，应带 %，实际 {raw!r}"
            else:
                assert raw.replace(",", "").isdigit(), f"「{label}」应是整数，实际 {raw!r}"
        return values

    # ================= 图表标题 =================
    def get_chart_titles(self) -> list:
        """获取所有图表卡片标题（已去空白、已过滤空标题）。"""
        elements = self.driver.find_elements(*self.CHART_HEADERS)
        titles = []
        for el in elements:
            try:
                t = (el.text or "").strip()
            except Exception:
                continue
            if t:
                titles.append(t)
        return titles

    def get_norm_titles(self) -> list:
        """标题归一后的列表，便于和期望值逐个对比。"""
        return [self.norm(t) for t in self.get_chart_titles()]

    def get_chart_title(self, index: int) -> str:
        titles = self.get_chart_titles()
        return titles[index] if index < len(titles) else ""

    def wait_chart_titles(self, need: int = 4, timeout: float = 20) -> list:
        """等图表标题凑够 need 个，返回原始标题 list。

        4 张图表卡片是常驻渲染的（有没有数据都渲染，没数据只是图里显示「暂无数据」），
        所以标题几乎立刻可读；这里显式等待是为了扛住路由切换/慢首屏。
        超时也返回 list（可能是空/不足），让后续断言给出可读原因，而不是 IndexError。
        """
        def _probe(_driver):
            try:
                titles = self.get_chart_titles() or []
            except Exception:
                return False
            return titles if len(titles) >= need else False

        try:
            return list(WebDriverWait(self.driver, timeout, poll_frequency=0.3).until(_probe))
        except Exception:
            try:
                got = list(self.get_chart_titles() or [])
            except Exception as e:
                got = []
                print(f"[STATS] ⚠️ get_chart_titles 抛异常：{type(e).__name__}: {e}")
            print(f"[STATS] ⚠️ {timeout}s 内只拿到 {len(got)} 个标题：{got}")
            return got

    def check_titles(self, expected: list, view: str, timeout: float = 20) -> list:
        """等标题就绪并逐个精确比对（用 `in` 会被「我的X」包含「X」骗过去）。"""
        titles = self.wait_chart_titles(need=len(expected), timeout=timeout)
        norm_titles = [self.norm(t) for t in titles]
        assert len(norm_titles) >= len(expected), (
            f"{view} 图表数量不足，期望至少 {len(expected)} 个，"
            f"实际 {len(norm_titles)} 个：{titles!r}"
        )
        for i, exp in enumerate(expected):
            act = norm_titles[i]
            assert act == exp, (
                f"{view} 第 {i + 1} 张图标题不对：实际 {titles[i]!r}，期望 {exp!r}；"
                f"全部标题：{titles!r}"
            )
        print(f"[STATS] {view} 图表标题全部匹配：{titles}")
        return titles

    def is_chart_empty(self, index: int) -> bool:
        """判断第 N 个图表（0 基）是否显示「暂无数据」。"""
        try:
            headers = self.driver.find_elements(*self.CHART_HEADERS)
            if index >= len(headers):
                return False
            parent = headers[index].find_element(
                By.XPATH, f"./ancestor::div[{_class_token('chart-card')}]")
            empty_el = parent.find_element(*self.CHART_EMPTY)
            return empty_el.is_displayed() and "暂无数据" in (empty_el.text or "")
        except Exception:
            return False

    # ================= 排查用 =================
    def debug_dump(self) -> dict:
        """一次性打印页面事实，用来核对文案/定位器。

        用法：print(stats_page.debug_dump())
        """
        cards = []
        for el in self.driver.find_elements(*self.STAT_CARD_ANY):
            try:
                label = (el.find_element(*self.STAT_LABEL).text or "").strip()
            except Exception:
                label = "<无 .stat-card__label>"
            value = ""
            for sub in (self.STAT_VALUE, self.STAT_PROGRESS):
                try:
                    value = (el.find_element(*sub).text or "").strip()
                    if value:
                        break
                except Exception:
                    continue
            cards.append({"label": label, "value": value, "raw": (el.text or "").strip()})

        dump = {
            "url": self.driver.current_url,
            "page_title": self._safe_text(self.PAGE_TITLE),
            "cards": cards,
            "chart_titles": self.get_chart_titles(),
        }
        print(f"[STATS-DUMP] {dump}")
        return dump

    def _safe_text(self, locator) -> str:
        try:
            return (self.visible(locator, timeout=3).text or "").strip()
        except Exception:
            return "<取不到>"
