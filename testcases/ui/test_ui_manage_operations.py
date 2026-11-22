"""后台配置管理 UI 用例（用户管理 + 项目成员权限）。

页面能力全部下沉到 POM：
    login_page.login_as(env, "admin")        → 登录编排、失败诊断
    user_manage_page.role_label("QA")        → QA / 测试 归一
    user_manage_page.form_errors()           → 提交没反应时的真实原因
    user_manage_page.get_row_status(user)    → 按表头「状态」列取 el-tag
    table_utils.column_values(driver, ...)   → 按表头取整列，避免 td[0] 拿到 ID

这里只留业务断言与数据清理。
"""
from __future__ import annotations

import uuid

import allure
import pytest

from utils.table_utils import column_values

# 系统里既有的验收项目名（不是 conftest 每次现造的 pytest-auto-proj-*）
TARGET_PROJECT = "轻舟自动化验收项目"

# 扫描项目名时用来剔除操作按钮那一列的文字
ACTION_WORDS = {"成员", "编辑", "删除", "详情", "查看", "配置", "缺陷", "任务"}


@allure.feature("UI 自动化")
@allure.story("后台配置管理")
class TestManageOperationsUI:

    @allure.title("ADMIN 新建用户：弹窗关闭、状态为「启用」、可清理")
    def test_create_user_flow(self, driver, env, login_page):
        from pages.user_manage_page import UserManagePage

        user_page = UserManagePage(driver, env["web_base_url"])
        username = f"ui_user_{uuid.uuid4().hex[:4]}"
        created = False
        deleted = False

        with allure.step("ADMIN 登录并进入用户管理"):
            login_page.login_as(env, "admin")
            user_page.open()

        try:
            with allure.step(f"创建新用户：{username}"):
                user_page.open_create_dialog()
                user_page.fill_form(
                    username=username,
                    password="123456",
                    real_name="UI测试账号",
                    # 传 value 也行：页面对象内部用 role_label 归一成「测试」
                    role_text="QA",
                )
                # submit_dialog 内部会把「弹窗没关」翻译成「表单校验错误」并附原因
                user_page.submit_dialog()
                created = True

            with allure.step("搜索并验证用户状态"):
                user_page.reset_search()      # 避免搜索框残留上一次关键词
                user_page.search(username=username)
                status = user_page.get_row_status(username)
                print(f"[MGMT] 新用户 {username} 状态 = {status!r}")
                assert status == "启用", f"新建用户状态应为「启用」，实际 {status!r}"

            with allure.step("删除该用户（清理数据）"):
                user_page.click_row_action(username, "删除")
                user_page.confirm_message_box()
                deleted = True

        finally:
            # 清理留在用例里：删除动作依赖当前 admin 会话和页面状态，
            # 夹具没法保证「此时浏览器还是 admin 身份、且停在这个页面」。
            if created and not deleted:
                try:
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

    @allure.title("PM 打开项目成员管理：应为可管理，不是只读")
    def test_project_member_readonly_check(self, driver, env, login_page, project_id):
        from pages.project_manage_page import ProjectManagePage

        proj_page = ProjectManagePage(driver, env["web_base_url"])

        with allure.step("PM 登录并进入项目列表"):
            login_page.login_as(env, "pm01")
            proj_page.open()

        with allure.step("定位要检查的项目"):
            # 按表头「项目名称」取列；第 1 列是 ID，直接取 td[0] 会拿到 ['324','226']
            names = column_values(driver, ("项目名称", "项目名", "名称"), fallback=2,
                                  exclude=ACTION_WORDS)
            print(f"[MGMT] PM 可见项目（{len(names)} 个）：{names[:8]}")
            if not names:
                pytest.skip("PM 的项目列表为空，无法验证成员权限（先确认 pm01 有可见项目）")

            if TARGET_PROJECT in names:
                target = TARGET_PROJECT
            elif env.get("project_name") in names:
                # conftest 自动造的项目，一定存在且 PM 可见
                target = env["project_name"]
                print(f"[MGMT] 未找到「{TARGET_PROJECT}」，改用 conftest 造的项目「{target}」")
            else:
                target = names[0]
                print(f"[MGMT] 未找到「{TARGET_PROJECT}」，改用列表首个项目「{target}」"
                      "（想固定目标就改文件顶部的 TARGET_PROJECT）")

        with allure.step(f"打开项目「{target}」的成员管理"):
            # 直接点行内按钮：PM 可见项目通常一页装得下，搜索框按哪个字段匹配没有文档
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
