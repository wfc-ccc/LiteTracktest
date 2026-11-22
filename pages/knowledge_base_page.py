"""知识库页面 POM。

源码是 frontend/views/knowledge/KnowledgeBase.vue（根节点 `.knowledge-base`，外层是 PageTable 组件）。

========== 源码事实（必须对齐，别自己猜） ==========
1. 布局：`PageTable` 里 `#search` 槽渲染 `.search-toolbar`，
   左侧 `.search-form`（字段 label「文件名」，input placeholder「搜索文件名」，按钮「搜索」「重置」），
   右侧 `.action-right` 放「上传知识」按钮 —— 该按钮 v-if="isAdmin"，DEV 看不到（节点不存在，不是 disabled）。
2. 表格列：文件名 / [访问权限，仅 ADMIN 可见] / 上传时间 / 操作（fixed right）。
   行操作只有两个：`查看`（link，一直有）、`删除`（v-if="isAdmin"，DEV 没有）。
3. 上传弹窗：title「上传知识文件」，字段「文件」(el-upload，`auto-upload=false`，按钮「选择文件」)
   和「访问权限」(el-select)。footer 是「取消」「确定上传」。
   访问权限 option 的 label 很长：
     1 → 全员访问（员工可见，AI 可检索）
     2 → AI 可检索（员工不可见原文，AI 可读取回答）
     3 → 仅管理员（最高机密，员工与 AI 均不可访问）
   所以这里按「前缀包含」匹配，传「全员访问」也能选中。
4. 上传时前端起一个**全屏** ElLoading（`.el-loading-mask.is-fullscreen` 挂在 body 下），
   文案「正在解析文档并构建知识库向量，请稍候...」。必须等它消失，否则点什么都点不到。
5. 详情抽屉 `el-drawer`（size 50%，destroy-on-close，teleport 到 body）：
   header 自定义 `.drawer-header__title`（「查看文件：xxx」/「修改文件：xxx」）；
   body `.content-viewer`（v-loading），查看态 `.content-viewer__text`，编辑态 textarea；
   footer 两套：查看态「复制全文」「编辑(v-if isAdmin)」「关闭」，编辑态「取消」「保存」。
6. 删除确认是 ElMessageBox，title「警告」，确认按钮文案「确认删除」。
7. Toast 文案：上传成功 → 「上传成功」；保存 → 「保存成功」；删除 → 「已删除」。

========== 等待规范 ==========
全文件**不使用 time.sleep**，所有等待统一走 WebDriverWait：
- 单条件 → `_visible()` / `_wait_bool()`（内置 timeout + poll_frequency）；
- 复合条件（可见且未被遮罩、抽屉 ready、option 前缀匹配、按钮 enabled）
  → 直接把判断写成 condition 函数交给 WebDriverWait 轮询。
`time` 只用于打点计时，不用于睡眠。
"""
from __future__ import annotations

import os
import time

from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from pages.base_page import BasePage

# 轮询期间可以容忍的瞬态异常：Vue patch 会把节点换掉，find_elements 可能撞上过期句柄
WAIT_IGNORED = (NoSuchElementException, StaleElementReferenceException)


class KnowledgeBasePage(BasePage):

    # ---------- 页面容器 ----------
    ROOT = (By.CSS_SELECTOR, ".knowledge-base")
    SEARCH_TOOLBAR = (By.CSS_SELECTOR, ".search-toolbar")
    SEARCH_FORM = (By.CSS_SELECTOR, ".search-form")
    TABLE = (By.CSS_SELECTOR, ".el-table")

    # ---------- 搜索区 ----------
    SEARCH_INPUT = (By.CSS_SELECTOR, ".search-form input[placeholder='搜索文件名']")
    BTN_SEARCH = (
        By.XPATH,
        "//div[contains(@class,'search-form')]//button[contains(normalize-space(),'搜索')]",
    )
    BTN_RESET = (
        By.XPATH,
        "//div[contains(@class,'search-form')]//button[contains(normalize-space(),'重置')]",
    )

    # ---------- 上传按钮（v-if isAdmin） ----------
    BTN_UPLOAD = (
        By.XPATH,
        "//div[contains(@class,'action-right')]//button[contains(normalize-space(),'上传知识')]",
    )

    # ---------- 表格行 / 行操作 ----------
    # 注意 el-table 的格子是 <td><div class="cell">文本</div></td>，
    # normalize-space() 对 td 会拼上全部子文本，正好等于文件名
    ROW = (By.XPATH, "//tr[.//td[normalize-space()='{filename}']]")
    ROW_ACTION_BTN = (
        By.XPATH,
        "//tr[.//td[normalize-space()='{filename}']]"
        "//button[contains(normalize-space(),'{btn_text}')]",
    )
    COL_ACCESS_LEVEL_HEADER = (
        By.XPATH,
        "//th//div[contains(normalize-space(),'访问权限')]",
    )
    EMPTY_BLOCK = (By.CSS_SELECTOR, ".el-table__empty-block")

    # ---------- 上传弹窗 ----------
    DIALOG = (By.CSS_SELECTOR, ".el-dialog")
    DIALOG_TITLE = (By.CSS_SELECTOR, ".el-dialog__title")
    DIALOG_FILE_INPUT = (By.CSS_SELECTOR, ".el-dialog input[type='file']")
    DIALOG_ACCESS_SELECT = (
        By.XPATH,
        "//div[contains(@class,'el-dialog')]//label[contains(normalize-space(),'访问权限')]"
        "/following-sibling::div//div[contains(@class,'el-select')]",
    )
    DIALOG_FOOTER_BTN = (
        By.XPATH,
        "//*[contains(@class,'el-dialog__footer')]//button[contains(normalize-space(),'{btn_text}')]",
    )
    SELECT_OPTION = (By.CSS_SELECTOR, ".el-select-dropdown__item")

    # ---------- 详情抽屉 ----------
    DRAWER = (By.CSS_SELECTOR, ".el-drawer")
    DRAWER_TITLE = (By.CSS_SELECTOR, ".drawer-header__title")
    DRAWER_CONTENT = (By.CSS_SELECTOR, ".content-viewer__text")
    DRAWER_TEXTAREA = (By.CSS_SELECTOR, ".content-viewer textarea")
    DRAWER_EMPTY = (By.CSS_SELECTOR, ".content-viewer .el-empty")
    DRAWER_BTN = (
        By.XPATH,
        "//div[contains(@class,'el-drawer')]//button[contains(normalize-space(),'{btn_text}')]",
    )

    # ---------- 全局元素 ----------
    GLOBAL_LOADING = (By.CSS_SELECTOR, ".el-loading-mask")
    # ElLoading.service({lock:true}) 生成的是全屏遮罩，和表格/抽屉自己的 loading 区分开
    FULLSCREEN_LOADING = (By.CSS_SELECTOR, ".el-loading-mask.is-fullscreen")
    MESSAGE = (By.CSS_SELECTOR, ".el-message")
    MESSAGE_BOX = (By.CSS_SELECTOR, ".el-message-box")

    # ===================================================================
    # 显式等待基础设施
    # ===================================================================
    @staticmethod
    def _wait(driver, timeout: float, poll: float = 0.2) -> WebDriverWait:
        return WebDriverWait(driver, timeout, poll_frequency=poll, ignored_exceptions=WAIT_IGNORED)

    def _wait_bool(self, cond, timeout: float, poll: float = 0.2) -> bool:
        """cond(driver) -> bool；True 立刻返回 True，超时返回 False。替代手写 while+sleep。"""
        try:
            self._wait(self.driver, timeout, poll).until(lambda d: True if cond(d) else False)
            return True
        except TimeoutException:
            return False

    def _visible(self, locator, timeout: float = 0, poll: float = 0.2) -> list:
        """当前可见的元素列表；timeout>0 时用显式等待轮询到出现（返回 [] 表示没等到）。"""
        def _probe(d):
            return [e for e in d.find_elements(*locator) if self._safe_displayed(e)] or False

        if timeout and timeout > 0:
            try:
                return self._wait(self.driver, timeout, poll).until(_probe)
            except TimeoutException:
                return []
        return _probe(self.driver) or []

    def wait_gone(self, locator, timeout: float = 15, poll: float = 0.2) -> bool:
        """等元素不再可见（或已从 DOM 移除）。"""
        return self._wait_bool(
            lambda d: not [e for e in d.find_elements(*locator) if self._safe_displayed(e)],
            timeout, poll,
        )

    # ===================================================================
    # 页面打开
    # ===================================================================
    def open(self, path: str = "/knowledge", wait_list: bool = True) -> None:
        """打开知识库页。路由不在 /knowledge 时把 path 传进来覆盖即可。

        wait_list=True 时等首屏 getList() 结束（表格 loading 撤掉）。
        进页面后「上传知识」点不动，通常就是在等这个请求：
        PageTable 把 v-loading 加在整个容器上，列表没回来之前搜索区和上传按钮都被遮罩压着。
        """
        t0 = time.time()
        self.open_path(path)
        self.wait_page_ready()
        print(f"[KB] ✅ 已打开知识库：{self.driver.current_url}"
              f"（容器渲染 {time.time() - t0:.1f}s）")

        if wait_list:
            t1 = time.time()
            self.wait_list_idle(timeout=30)
            print(f"[KB] ✅ 首屏列表加载完成（导航到列表就绪共 {time.time() - t0:.1f}s，"
                  f"其中等列表 {time.time() - t1:.1f}s）")

    def wait_page_ready(self, timeout: int = 20) -> None:
        ok = self._wait_bool(
            lambda d: bool(self._visible(self.SEARCH_TOOLBAR) or self._visible(self.ROOT)),
            timeout,
        )
        if ok:
            print("[KB] ✅ 知识库容器已渲染")
            return
        print(f"[KB] ⚠️ 页面未渲染，当前 URL：{self.driver.current_url}")
        raise AssertionError(
            f"知识库页面没有渲染（{self.driver.current_url}）。"
            "若路由不是 /knowledge，请调用 open(path='/xxx') 指定"
        )

    # ===================================================================
    # 通用工具
    # ===================================================================
    @staticmethod
    def _safe_displayed(el) -> bool:
        try:
            return bool(el.is_displayed())
        except Exception:
            return False

    @staticmethod
    def _txt(el) -> str:
        try:
            return " ".join((el.text or "").split())
        except Exception:
            return ""

    def _displayed(self, locator, timeout: float = 0) -> list:
        """兼容旧调用名，内部改走 WebDriverWait。"""
        return self._visible(locator, timeout=timeout)

    def _unoccluded(self, el) -> bool:
        """元素是否真的能点到：用它中心的 elementFromPoint 判断有没有被遮罩盖住。

        知识库的 PageTable 是 <PageTable :loading="loading">，
        getList() 期间整块区域（含搜索区和右上角「上传知识」）会被
        .el-loading-mask 半透明遮罩压住 —— 此时 is_displayed() 仍是 True，
        但真实点击会被拦截。这正是「进页面后要卡一会儿才能点上传」的原因。
        """
        try:
            return bool(self.driver.execute_script(
                """
                const el = arguments[0];
                const r = el.getBoundingClientRect();
                if (!r || r.width === 0 || r.height === 0) return false;
                const x = r.left + r.width / 2, y = r.top + r.height / 2;
                const top = document.elementFromPoint(x, y);
                if (!top) return false;
                return top === el || el.contains(top) || top.contains(el);
                """,
                el,
            ))
        except Exception:
            return False

    def wait_clickable(self, locator, timeout: int = 30, tag: str = "",
                       poll: float = 0.3):
        """等元素可见**且没被 loading 遮罩盖住**，返回该元素。

        复合条件（可见 + 不被遮挡）交给 WebDriverWait 轮询，
        poll_frequency 由参数控制，不再自己 while + sleep。
        """
        t0 = time.time()

        def _ready(d):
            for e in d.find_elements(*locator):
                if self._safe_displayed(e) and self._unoccluded(e):
                    return e
            return False

        try:
            el = self._wait(self.driver, timeout, poll).until(_ready)
        except TimeoutException:
            masks = [m for m in self.driver.find_elements(*self.FULLSCREEN_LOADING)
                     if self._safe_displayed(m)]
            self.dump_list(tag=f"等待「{tag or locator}」可点超时")
            raise AssertionError(
                f"等「{tag or locator}」可点击超时（{timeout}s）：全屏遮罩={len(masks)}，"
                "多半是列表接口还没返回、遮罩没撤"
            )
        if tag:
            print(f"[KB] ✅ {tag} 可点击（耗时 {time.time() - t0:.1f}s）")
        return el

    def _click_el(self, el) -> None:
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        except Exception:
            pass
        try:
            el.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", el)

    def is_element_visible(self, locator, timeout: int = 0) -> bool:
        """元素当前是否可见（timeout>0 时轮询）。DEV 看不到的按钮会直接返回 False。"""
        if timeout:
            return bool(self._visible(locator, timeout=timeout))
        return any(self._safe_displayed(e) for e in self.driver.find_elements(*locator))

    def _masks(self, locator, d=None) -> list:
        d = d or self.driver
        return [m for m in d.find_elements(*locator) if self._safe_displayed(m)]

    def wait_loading_off(self, timeout: int = 120, appear: float = 3.0,
                         poll: float = 0.4) -> None:
        """等**全屏** loading 消失（上传后端的解析 + 向量化）。

        慢的根源在这里：handleConfirmUpload 是
          openUploadLoading() → await uploadKnowledge(payload) → success
        即 ElLoading.service({lock:true}) 把整个页面锁死，一直等到后端解析返回。

        显式等待分两阶段：
        1. 先在 appear 秒内等遮罩**出现**（点完按钮到 Vue 挂上遮罩有几十毫秒，直接判消失会误报 0.0s）；
        2. 再用 WebDriverWait 等它消失，poll_frequency 0.4s，每 5s 打一行进度。
        """
        t0 = time.time()
        appeared = self._wait_bool(lambda d: bool(self._masks(self.FULLSCREEN_LOADING)),
                                   min(appear, timeout), poll=0.1)
        if not appeared:
            print("[KB] 未观察到全屏遮罩（请求可能极快已完成，或提交被前端校验拦下）")

        state = {"next": 5}

        def _still_loading(d):
            if not self._masks(self.FULLSCREEN_LOADING, d):
                return True
            elapsed = time.time() - t0
            if elapsed >= state["next"]:
                print(f"[KB] …后端解析中，已等待 {elapsed:.0f}s")
                state["next"] += 5
            return False

        if self._wait_bool(_still_loading, timeout, poll=poll):
            print(f"[KB] ✅ 全屏 loading 消失，耗时 {time.time() - t0:.1f}s")
            return
        elapsed = time.time() - t0
        print(f"[KB] ⚠️ 全屏 loading 已等待 {elapsed:.0f}s，仍未消失")
        raise AssertionError(
            f"上传解析超时（{timeout}s）—— 后端可能很慢或接口报错；"
            "可调大 wait_loading_off(timeout=...)"
        )

    def wait_message(self, keyword: str, timeout: int = 20) -> str:
        """等 toast 出现（找不到会抛，提示当前所有 toast）"""
        def _match(d):
            for m in d.find_elements(*self.MESSAGE):
                if self._safe_displayed(m) and keyword in self._txt(m):
                    return self._txt(m)
            return False

        try:
            text = self._wait(self.driver, timeout, poll=0.15).until(_match)
        except TimeoutException:
            seen = [self._txt(m) for m in self.driver.find_elements(*self.MESSAGE)
                    if self._safe_displayed(m)]
            raise AssertionError(f"没等到提示「{keyword}」，当前提示：{seen}")
        print(f"[KB] ✅ 提示：{text}")
        return text

    # ===================================================================
    # 搜索列表
    # ===================================================================
    def wait_list_idle(self, timeout: int = 20, poll: float = 0.3) -> None:
        """等表格/抽屉自身的 loading 消失（显式等待，无 sleep）。"""
        if self._wait_bool(lambda d: not self._masks(self.GLOBAL_LOADING, d), timeout, poll=poll):
            return
        left = len(self._masks(self.GLOBAL_LOADING))
        print(f"[KB] ⚠️ 等列表 loading 超时（{timeout}s），仍有 {left} 个遮罩")

    def _force_input_value(self, el, value: str) -> None:
        """用原生 setter + input 事件写值。

        Selenium 的 clear() 在 Element Plus 的 el-input 上不一定能让 v-model 同步，
        再 send_keys 就会出现「旧值 + 新值」拼在一起，搜索直接返回 0 条。
        """
        self.driver.execute_script(
            """
            const el = arguments[0], val = arguments[1];
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
            setter.call(el, val);
            el.dispatchEvent(new Event('input', {bubbles: true}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
            """,
            el, value,
        )

    def search(self, keyword: str, timeout: int = 20) -> None:
        inputs = self._visible(self.SEARCH_INPUT, timeout=timeout)
        if not inputs:
            raise AssertionError("没找到搜索框 input[placeholder='搜索文件名']")
        el = inputs[0]

        try:
            el.clear()
        except Exception:
            pass
        self._force_input_value(el, "")

        try:
            el.click()
            el.send_keys(keyword)
        except Exception:
            self._force_input_value(el, keyword)

        actual = (el.get_attribute("value") or "")
        if actual != keyword:
            print(f"[KB] ⚠️ 搜索框实际值 {actual!r} != {keyword!r}，用 JS 兜底写入")
            self._force_input_value(el, keyword)
            actual = (el.get_attribute("value") or "")

        btns = self._visible(self.BTN_SEARCH, timeout=5)
        if btns:
            self._click_el(btns[0])
        else:
            from selenium.webdriver.common.keys import Keys
            el.send_keys(Keys.ENTER)

        # 结果以 wait_row / row_exists 的轮询为准，这里只等 loading 撤掉
        self.wait_list_idle(timeout=timeout)
        print(f"[KB] 已搜索：{actual}")
        if keyword and actual != keyword:
            raise AssertionError(
                f"搜索框里的值不对：期望 {keyword!r}，实际 {actual!r}"
            )

    def reset_search(self, timeout: int = 20) -> None:
        btns = self._visible(self.BTN_RESET, timeout=timeout)
        if btns:
            self._click_el(btns[0])
            self.wait_list_idle(timeout=timeout)

    def wait_row(self, filename: str, timeout: int = 20) -> bool:
        """等文件名出现在列表里"""
        loc = (self.ROW[0], self.ROW[1].replace("{filename}", filename))
        if self._visible(loc, timeout=timeout):
            print(f"[KB] ✅ 列表出现文件：{filename}")
            return True
        self.dump_list(tag=f"等待文件「{filename}」超时")
        return False

    def row_exists(self, filename: str, timeout: float = 0) -> bool:
        """列表里是否有这行；timeout>0 时轮询（表格重渲染有延迟，别立即判空）"""
        loc = (self.ROW[0], self.ROW[1].replace("{filename}", filename))
        return bool(self._visible(loc, timeout=timeout))

    def row_files(self) -> list:
        """当前页所有文件名（第一列）"""
        out = []
        for tr in self.driver.find_elements(By.CSS_SELECTOR, ".el-table__body tr"):
            tds = tr.find_elements(By.CSS_SELECTOR, "td")
            if tds:
                out.append(self._txt(tds[0]))
        return out

    def row_action_texts(self, filename: str) -> list:
        loc = (self.ROW[0], self.ROW[1].replace("{filename}", filename))
        rows = self._visible(loc)
        if not rows:
            return []
        return [self._txt(b) for b in rows[0].find_elements(By.TAG_NAME, "button")
                if self._safe_displayed(b)]

    def first_row_action_texts(self) -> list:
        for tr in self.driver.find_elements(By.CSS_SELECTOR, ".el-table__body tr"):
            btns = [self._txt(b) for b in tr.find_elements(By.TAG_NAME, "button")
                    if self._safe_displayed(b)]
            if btns:
                return btns
        return []

    def click_row_action(self, filename: str, btn_text: str, timeout: int = 20) -> None:
        if not self.wait_row(filename, timeout=timeout):
            raise AssertionError(f"列表里没有文件「{filename}」")
        loc = (self.ROW_ACTION_BTN[0],
               self.ROW_ACTION_BTN[1]
               .replace("{filename}", filename)
               .replace("{btn_text}", btn_text))
        btns = self._visible(loc, timeout=10)
        if not btns:
            raise AssertionError(
                f"「{filename}」这一行没有按钮「{btn_text}」"
                f"，实际按钮：{self.row_action_texts(filename)}"
            )
        self._click_el(btns[0])
        print(f"[KB] 点击行操作「{btn_text}」（{filename}）")

    def dump_list(self, tag: str = "当前列表") -> None:
        files = self.row_files()
        empty = any(self._safe_displayed(e) for e in self.driver.find_elements(*self.EMPTY_BLOCK))
        print(f"[KB] {tag}：共 {len(files)} 行{'（空表）' if empty else ''} → {files}")

    # ===================================================================
    # 上传
    # ===================================================================
    def dialog(self, keyword: str = "上传知识文件", timeout: int = 15):
        def _find(d):
            for dlg in d.find_elements(*self.DIALOG):
                if not self._safe_displayed(dlg):
                    continue
                title = ""
                for t in dlg.find_elements(*self.DIALOG_TITLE):
                    title = self._txt(t)
                    if title:
                        break
                if keyword in title:
                    return dlg
            return False

        try:
            return self._wait(self.driver, timeout, poll=0.2).until(_find)
        except TimeoutException:
            titles = [self._txt(t) for t in self.driver.find_elements(*self.DIALOG_TITLE)
                      if self._safe_displayed(t)]
            raise AssertionError(f"没有等到标题含「{keyword}」的弹窗，当前弹窗标题：{titles}")

    def open_upload_dialog(self, timeout: int = 30) -> None:
        """点「上传知识」并等弹窗出现。

        这里不用 is_displayed 判断就绪，而是等按钮「不被遮罩盖住」——
        PageTable 的 v-loading 会罩住整个容器（含右上角上传按钮），
        进页面后必须先等 getList() 返回、遮罩撤掉，按钮才真正点得动。
        """
        try:
            btn = self.wait_clickable(self.BTN_UPLOAD, timeout=timeout, tag="「上传知识」按钮")
        except AssertionError:
            raise AssertionError(
                "没有可点击的「上传知识」按钮 —— 该按钮是 v-if=\"isAdmin\"，"
                "要么当前账号不是 ADMIN，要么列表还在加载、遮罩没撤"
            )
        self._click_el(btn)
        self.dialog(timeout=timeout)
        print("[KB] ✅ 上传弹窗已打开")

    def _dialog_btn(self, btn_text: str, dlg=None, timeout: int = 15, wait_enabled: bool = True):
        """footer 是 <footer class="el-dialog__footer">，不能用 //div 限定"""
        d = dlg or self.dialog()
        norm = "".join(btn_text.split())

        def _find(driver):
            for b in d.find_elements(By.TAG_NAME, "button"):
                if not self._safe_displayed(b):
                    continue
                t = "".join(self._txt(b).split())
                if wait_enabled and not self._safe_enabled(b):
                    continue
                if t == norm or norm in t:
                    return b
            return False

        try:
            return self._wait(self.driver, timeout, poll=0.2).until(_find)
        except TimeoutException:
            diag = []
            for b in d.find_elements(By.TAG_NAME, "button"):
                if not self._safe_displayed(b):
                    continue
                t = "".join(self._txt(b).split())
                loading = "is-loading" in (b.get_attribute("class") or "")
                diag.append(f"{t!r}(enabled={self._safe_enabled(b)}, loading={loading})")
            raise AssertionError(f"弹窗里没找到按钮「{btn_text}」，当前按钮：{diag}")

    @staticmethod
    def _safe_enabled(el) -> bool:
        try:
            return bool(el.is_enabled())
        except Exception:
            return False

    def _select_access_level(self, access_level: str, dlg, timeout: int = 10) -> None:
        """访问权限下拉：option label 很长，按前缀包含匹配"""
        sel = dlg.find_elements(*self.DIALOG_ACCESS_SELECT)
        if not sel:
            raise AssertionError("弹窗里没找到「访问权限」下拉")
        self._click_el(sel[0])

        norm = "".join(access_level.split())

        def _pick(driver):
            for o in driver.find_elements(*self.SELECT_OPTION):
                if not self._safe_displayed(o):
                    continue
                if norm in "".join(self._txt(o).split()):
                    return o
            return False

        try:
            opt = self._wait(self.driver, timeout, poll=0.15).until(_pick)
        except TimeoutException:
            raise AssertionError(
                f"访问权限下拉里没有含「{access_level}」的选项，"
                f"可见选项：{[self._txt(o) for o in self.driver.find_elements(*self.SELECT_OPTION)]}"
            )
        self._click_el(opt)
        print(f"[KB] 访问权限选「{self._txt(opt)}」")

    def select_file(self, file_path: str, dlg=None) -> None:
        """给 el-upload 的隐藏 input 塞文件（input 可能 display:none，直接用 find_elements）"""
        d = dlg or self.dialog()
        abs_path = os.path.abspath(file_path)
        if not os.path.isfile(abs_path):
            raise FileNotFoundError(f"文件不存在：{abs_path}")
        inputs = d.find_elements(*self.DIALOG_FILE_INPUT)
        if not inputs:
            raise AssertionError("弹窗里没有 input[type='file']")
        inputs[0].send_keys(abs_path)
        print(f"[KB] 已选择文件：{abs_path}")

    def upload_file(self, file_path: str, access_level: str = "", timeout: int = 60) -> None:
        """上传：选文件 → 等文件项回填 → 选访问权限 → 点确定上传 → 等全屏 loading 消失、弹窗关闭"""
        dlg = self.dialog()
        self.select_file(file_path, dlg)

        if not self._visible((By.CSS_SELECTOR, ".el-upload-list__item"), timeout=10):
            print("[KB] ⚠️ 文件项未出现在上传列表，继续尝试提交")

        if access_level:
            self._select_access_level(access_level, dlg)

        btn = self._dialog_btn("确定上传", dlg, timeout=10)
        t0 = time.time()
        self._click_el(btn)
        print("[KB] 已点击「确定上传」")

        self.wait_loading_off(timeout=timeout)
        if self.wait_gone(self.DIALOG, timeout=timeout, poll=0.2):
            print(f"[KB] ✅ 上传弹窗已关闭，后端解析共耗时 {time.time() - t0:.1f}s")
            return
        raise AssertionError("点「确定上传」后弹窗没有关闭（可能校验失败，看页面 toast）")

    # ===================================================================
    # 详情抽屉
    # ===================================================================
    def drawer(self, timeout: int = 15):
        els = self._visible(self.DRAWER, timeout=timeout)
        if not els:
            raise AssertionError("详情抽屉没有打开")
        return els[0]

    def open_drawer_for(self, filename: str, timeout: int = 20) -> None:
        """点行内「查看」并**等抽屉真正出现**。

        点击后 Vue 才把 drawerVisible 置为 true，DOM 下一帧才渲染；
        点完立刻查 .el-drawer 必然是空的，所以要显式等待。
        """
        self.click_row_action(filename, "查看", timeout=timeout)
        if not self._visible(self.DRAWER, timeout=timeout):
            self._dump_drawer_state()
            raise AssertionError("点击「查看」后详情抽屉没有打开")
        print(f"[KB] ✅ 详情抽屉已打开（{filename}）")

    def _dump_drawer_state(self, tag: str = "抽屉状态") -> None:
        drawers = self.driver.find_elements(*self.DRAWER)
        overlays = self.driver.find_elements(By.CSS_SELECTOR, ".el-overlay")
        print(f"[KB] {tag}：.el-drawer={len(drawers)}，.el-overlay={len(overlays)}")
        for d in drawers:
            print(f"[KB]   drawer class={d.get_attribute('class')} "
                  f"displayed={self._safe_displayed(d)}")
        for o in overlays:
            print(f"[KB]   overlay class={o.get_attribute('class')} "
                  f"displayed={self._safe_displayed(o)}")

    def drawer_title(self) -> str:
        dr = self.drawer()
        ts = dr.find_elements(*self.DRAWER_TITLE)
        return self._txt(ts[0]) if ts else ""

    def wait_drawer_content(self, timeout: int = 30) -> None:
        """等抽屉出现并加载完内容：loading 消失，且正文或空态出现。"""
        if not self._visible(self.DRAWER, timeout=timeout):
            self._dump_drawer_state()
            raise AssertionError("详情抽屉没有打开（点击「查看」后一直不可见）")

        def _ready(d):
            drawers = [x for x in d.find_elements(*self.DRAWER) if self._safe_displayed(x)]
            if not drawers:
                return False          # 可能正在关闭，继续等到超时再判定
            dr = drawers[0]
            if self._masks(self.GLOBAL_LOADING, dr):
                return False
            return bool(dr.find_elements(*self.DRAWER_CONTENT)
                        or dr.find_elements(*self.DRAWER_TEXTAREA)
                        or dr.find_elements(*self.DRAWER_EMPTY))

        if not self._wait_bool(_ready, timeout, poll=0.2):
            self._dump_drawer_state("抽屉内容加载超时")
            print(f"[KB] ⚠️ 抽屉内容在 {timeout}s 内没有就绪（正文/空态都没出现）")

    def get_drawer_content(self) -> str:
        """查看态取正文；编辑态取 textarea 的值"""
        self.wait_drawer_content()
        dr = self.drawer()
        ta = dr.find_elements(*self.DRAWER_TEXTAREA)
        if ta:
            return ta[0].get_attribute("value") or ""
        node = dr.find_elements(*self.DRAWER_CONTENT)
        return self._txt(node[0]) if node else ""

    def click_drawer_btn(self, btn_text: str, timeout: int = 15) -> None:
        loc = (self.DRAWER_BTN[0], self.DRAWER_BTN[1].replace("{btn_text}", btn_text))
        btns = self._visible(loc, timeout=timeout)
        if not btns:
            dr = self.drawer()
            here = [self._txt(b) for b in dr.find_elements(By.TAG_NAME, "button")
                    if self._safe_displayed(b)]
            raise AssertionError(f"抽屉里没有按钮「{btn_text}」，当前按钮：{here}")
        self._click_el(btns[0])
        print(f"[KB] 点击抽屉按钮「{btn_text}」")

    def close_drawer(self, timeout: int = 15) -> None:
        try:
            self.click_drawer_btn("关闭", timeout=timeout)
        except AssertionError:
            self.driver.execute_script(
                "document.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', bubbles:true}));"
            )
        if self.wait_gone(self.DRAWER, timeout=timeout, poll=0.2):
            print("[KB] ✅ 抽屉已关闭")
            return
        raise AssertionError("抽屉没有关闭")

    def set_edit_content(self, content: str) -> None:
        tas = self._visible(self.DRAWER_TEXTAREA, timeout=10)
        if not tas:
            raise AssertionError("当前不在编辑态（抽屉里没有 textarea）")
        ta = tas[0]
        try:
            ta.clear()
        except Exception:
            self.driver.execute_script("arguments[0].value='';", ta)
        ta.send_keys(content)
        print(f"[KB] 已填写编辑内容（{len(content)} 字符）")

    def view_file(self, filename: str, timeout: int = 20) -> str:
        """查看文件 → 取正文（抽屉不关）；内部会先等抽屉真正打开"""
        self.open_drawer_for(filename, timeout=timeout)
        return self.get_drawer_content()

    def delete_file(self, filename: str, confirm: bool = True, timeout: int = 30) -> None:
        """删除：行内删除 → 确认框「确认删除」"""
        self.click_row_action(filename, "删除", timeout=timeout)

        boxes = self._visible(self.MESSAGE_BOX, timeout=timeout)
        if not boxes:
            raise AssertionError("删除确认框没有弹出")

        label = "确认删除" if confirm else "取消"
        for b in boxes[0].find_elements(By.TAG_NAME, "button"):
            if self._safe_displayed(b) and label in self._txt(b):
                self._click_el(b)
                print(f"[KB] 删除确认框点「{label}」")
                break
        else:
            raise AssertionError("删除确认框里没找到按钮")

        if confirm:
            self.wait_message("已删除", timeout=timeout)
            self.wait_list_idle()

    def delete_if_exists(self, filename: str, timeout: int = 10) -> bool:
        """同名文件存在就先删掉，保证用例可重复执行。

        用固定素材（data/uplodedata/知识库.txt）之后，重复跑会遇到重名，
        后端很可能直接返回「文件已存在」，所以上传前先清一遍。
        """
        self.reset_search()
        self.wait_list_idle()
        if self.row_exists(filename, timeout=timeout):
            self.delete_file(filename)
            print(f"[KB] ✅ 已删除同名旧文件：{filename}")
            return True
        print(f"[KB] 列表里没有同名文件 {filename}，无需清理")
        return False

    def cleanup_by_prefix(self, prefix: str, max_rounds: int = 5) -> int:
        """按文件名前缀清理历史残留（自动化专用前缀，幂等）。

        知识库是全局数据，用例跑失败时 finally 未必删干净，
        残留会一直堆积（就看到过 2 个 UI测试文档_ 挂在列表里）。
        """
        self.reset_search()
        self.wait_list_idle()
        removed = 0
        for _ in range(max_rounds):
            targets = [f for f in self.row_files() if f.startswith(prefix)]
            if not targets:
                break
            for f in targets:
                try:
                    self.delete_file(f)
                    removed += 1
                except Exception as e:
                    print(f"[KB-CLEANUP] ⚠️ 删除 {f} 失败：{type(e).__name__}: {e}")
                    return removed
            self.reset_search()
            self.wait_list_idle()
        if removed:
            print(f"[KB-CLEANUP] ✅ 清理前缀「{prefix}」共 {removed} 个")
        return removed

    # ===================================================================
    # 身份诊断
    # 源码里 isAdmin = userStore.role === 'ADMIN'（严格比较），
    # 只注入 litetrack_token 不一定能还原 role，这里把真实值打出来。
    # ===================================================================
    def local_storage(self) -> dict:
        try:
            return self.driver.execute_script(
                "return Object.assign({}, window.localStorage);"
            ) or {}
        except Exception as e:
            return {"__error__": str(e)}

    def current_role(self):
        """扫 localStorage 里所有 JSON 值，找 role 字段"""
        js = """
        for (const k of Object.keys(localStorage)) {
            try {
                const v = JSON.parse(localStorage.getItem(k));
                if (v && typeof v === 'object') {
                    if (v.role) return v.role;
                    if (v.userInfo && v.userInfo.role) return v.userInfo.role;
                }
            } catch (e) {}
        }
        return null;
        """
        try:
            return self.driver.execute_script(js)
        except Exception:
            return None

    def debug_identity(self, tag: str = "身份诊断") -> None:
        print(f"[KB-AUTH] ---- {tag} ----")
        print(f"[KB-AUTH] URL = {self.driver.current_url}")
        for k, v in self.local_storage().items():
            print(f"[KB-AUTH] localStorage[{k}] = {str(v)[:200]}")
        print(f"[KB-AUTH] 探测到的 role = {self.current_role()!r}")
        print(f"[KB-AUTH] 上传按钮可见 = {self.is_element_visible(self.BTN_UPLOAD)}")
        print(f"[KB-AUTH] 访问权限列可见 = {self.is_element_visible(self.COL_ACCESS_LEVEL_HEADER)}")
        print(f"[KB-AUTH] 列表行数 = {len(self.row_files())} → {self.row_files()[:5]}")
        print("[KB-AUTH] --------------------")
