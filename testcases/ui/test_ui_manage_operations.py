import re

import allure
import pytest
import uuid

from selenium.webdriver.common.by import By

# 前端 UserManage.vue 里 ROLE_OPTIONS 的 label（下拉里显示的是这些中文）
ROLE_LABELS = {
    "ADMIN": "管理员",
    "PM": "项目经理",
    "DEV": "开发",
    "QA": "测试",
}
# value 和 label 都接受，避免再因为「传 QA 还是传测试」踩坑
ROLE_ALIASES = {**ROLE_LABELS, **{v: v for v in ROLE_LABELS.values()}}

# 系统里既有的验收项目名（不是 conftest 每次现造的 pytest-auto-proj-*）
TARGET_PROJECT = "轻舟自动化验收项目"
# 扫描行文本时用来剔除操作按钮那一列
ACTION_WORDS = {"成员", "编辑", "删除", "详情", "查看", "配置", "缺陷", "任务"}

# td/th 的 class 形如 el-table_1_column_3，用它精确取列
COLUMN_CLASS_RE = re.compile(r"el-table_\d+_column_(\d+)")


def _role_label(text: str) -> str:
    """把 QA / 测试 都归一成下拉里真实的 label（select_real 是按可见文本匹配的）。"""
    return ROLE_ALIASES.get(text.strip().upper(), text.strip())


def _login_via_ui(driver, env, account: str, password: str | None = None):
    """真实 UI 登录。本文件内自包含，不依赖 utils.ui_login。

    为什么不注入 token：
    1. 新会话 driver 停在 `data:,`，在那里读写 localStorage 会抛
       「Storage is disabled inside 'data:' URLs」，页面都进不去；
    2. 即使先导航到同源再注入，`userStore.role` 也不会还原，
       依赖 isAdmin 的入口（新建用户、删除）会判成不存在，得到假阴性。
    """
    from pages.login_page import LoginPage

    acc = (env.get("accounts") or {}).get(account) or {}
    username = acc.get("username") or account
    pwd = password or acc.get("password") or "123456"

    page = LoginPage(driver, env["web_base_url"])
    page.open()                      # 内部已处理 data: 兜底 + 清 token + 进 /login
    page.wait_login_page_display()
    page.login(username=username, password=pwd)
    name = page.wait_until_logged_in()
    print(f"[AUTH] ✅ UI 登录成功：{username}（顶栏 {name}），URL={driver.current_url}")
    return page


def _form_errors(driver) -> list:
    """当前弹窗里的表单校验错误（submit 没反应时最有用的信息）。"""
    out = []
    for e in driver.find_elements(By.CSS_SELECTOR, ".el-form-item__error"):
        try:
            if e.is_displayed():
                t = (e.text or "").strip()
                if t:
                    out.append(t)
        except Exception:
            continue
    return out


# ======================================================================
# 表格读取：按表头定位列，不要直接取 td[0]
# 项目列表第一列是 ID（上一轮扫出来是 ['324','226']，就是 ID 不是项目名）
# ======================================================================
def _table_headers(driver) -> list:
    return [" ".join((th.text or "").split())
            for th in driver.find_elements(By.CSS_SELECTOR, ".el-table__header th")]


def _column_index(driver, keywords) -> int | None:
    """按表头文本找列序号（1-based），找不到返回 None。"""
    for i, th in enumerate(driver.find_elements(By.CSS_SELECTOR, ".el-table__header th"), start=1):
        text = " ".join((th.text or "").split())
        if any(k in text for k in keywords):
            return i
    return None


def _cell_text(tr, idx: int) -> str:
    """按列序号取单元格文本（td 的 class 带 el-table_N_column_M）。"""
    for td in tr.find_elements(By.CSS_SELECTOR, "td"):
        m = COLUMN_CLASS_RE.search(td.get_attribute("class") or "")
        if m and int(m.group(1)) == idx:
            return " ".join((td.text or "").split())
    tds = tr.find_elements(By.CSS_SELECTOR, "td")
    if 0 < idx <= len(tds):
        return " ".join((tds[idx - 1].text or "").split())
    return ""


def _project_names(driver) -> list:
    """取项目名称列的所有值（表头找不到就用第 2 列，第 1 列通常是 ID）。"""
    idx = _column_index(driver, ("项目名称", "项目名", "名称"))
    if idx is None:
        idx = 2
        print("[MGMT] ⚠️ 表头里没找到「项目名称」，退到第 2 列取值")

    names = []
    for tr in driver.find_elements(By.CSS_SELECTOR, ".el-table__body tr"):
        if not tr.find_elements(By.CSS_SELECTOR, "td"):
            continue
        name = _cell_text(tr, idx)
        if name and name not in ACTION_WORDS and name not in names:
            names.append(name)
    return names


@allure.feature("UI 自动化")
@allure.story("后台配置管理")
class TestManageOperationsUI:

    def test_create_user_flow(self, driver, env):
        from pages.user_manage_page import UserManagePage

        user_page = UserManagePage(driver, env["web_base_url"])
        username = f"ui_user_{uuid.uuid4().hex[:4]}"
        created = False
        deleted = False

        with allure.step("ADMIN 登录并进入用户管理"):
            _login_via_ui(driver, env, "admin")
            user_page.open()

        try:
            with allure.step(f"创建新用户：{username}"):
                user_page.open_create_dialog()
                user_page.fill_form(
                    username=username,
                    password="123456",
                    real_name="UI测试账号",
                    # 关键：下拉里显示的是「测试」，value 才是 QA。
                    # select_real 按可见文本匹配，传 QA 会找不到选项
                    role_text=_role_label("QA"),
                )
                try:
                    user_page.submit_dialog()
                except AssertionError as e:
                    # submitForm 里 validate() 不通过就直接 return，弹窗不关，
                    # 表现是「等弹窗关闭超时」，真正原因在 .el-form-item__error
                    raise AssertionError(
                        f"提交后弹窗未关闭，表单校验错误：{_form_errors(driver)}（原文：{e}）"
                    ) from e
                created = True

            with allure.step("搜索并验证用户状态"):
                user_page.search(username=username)
                status = user_page.get_row_status(username)
                print(f"[MGMT] 新用户 {username} 状态 = {status!r}")
                assert status == "启用", f"新建用户状态应为「启用」，实际 {status!r}"

            with allure.step("删除该用户（清理数据）"):
                user_page.click_row_action(username, "删除")
                user_page.confirm_message_box()
                deleted = True

        finally:
            if created and not deleted:
                try:
                    # 先重置再搜：避免搜索框里残留上一次的关键词
                    user_page.reset_search()
                    user_page.search(username=username)
                    if user_page.is_action_btn_exist(username, "删除"):
                        user_page.click_row_action(username, "删除")
                        user_page.confirm_message_box()
                        print(f"[MGMT-CLEANUP] ✅ 已删除残留用户 {username}")
                    else:
                        print(f"[MGMT-CLEANUP] 列表里已没有 {username}，无需清理")
                except Exception as e:
                    print(f"[MGMT-CLEANUP] ⚠️ 清理用户 {username} 失败（不影响主断言）："
                          f"{type(e).__name__}: {e}")

    def test_project_member_readonly_check(self, driver, env, project_id):
        from pages.project_manage_page import ProjectManagePage

        proj_page = ProjectManagePage(driver, env["web_base_url"])

        with allure.step("PM 登录并进入项目列表"):
            _login_via_ui(driver, env, "pm01")
            proj_page.open()

        with allure.step("定位要检查的项目"):
            heads = _table_headers(driver)
            print(f"[MGMT] 项目列表表头：{heads}")

            names = _project_names(driver)
            print(f"[MGMT] PM 可见项目（{len(names)} 个）：{names[:8]}")
            if not names:
                pytest.skip("PM 的项目列表为空，无法验证成员权限（先确认 pm01 有可见项目）")

            target = TARGET_PROJECT if TARGET_PROJECT in names else names[0]
            if target != TARGET_PROJECT:
                print(f"[MGMT] 未找到「{TARGET_PROJECT}」，改用列表首个项目「{target}」"
                      "（想固定目标就改文件顶部的 TARGET_PROJECT）")

        with allure.step(f"打开项目「{target}」的成员管理"):
            # 直接点行内按钮：PM 可见项目通常一页就能装下，
            # 搜索框究竟按哪个字段匹配没有文档，先不动它
            try:
                proj_page.click_row_action(target, "成员")
            except Exception as first:
                print(f"[MGMT] 直接点「成员」失败（{type(first).__name__}），改用搜索后再点")
                proj_page.search(name=target)
                proj_page.click_row_action(target, "成员")

        with allure.step("验证成员弹窗渲染，且 PM 不是只读"):
            readonly = proj_page.is_member_readonly()
            print(f"[MGMT] is_member_readonly() = {readonly!r}")
            assert readonly is False, (
                f"PM 应该能管理项目成员，实际 is_member_readonly={readonly!r}"
                "（None 说明该方法没拿到弹窗，要看 ProjectManagePage 的实现）"
            )
