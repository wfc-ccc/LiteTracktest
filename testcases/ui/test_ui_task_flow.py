"""任务看板核心流转 UI 用例。

产品规则决定了这条链路天然横跨两个身份：新建任务只对 ADMIN / PM 开放，
接受任务只有负责人本人（isAssignee）能操作。所以在同一个类里放两条用例，
各自主管一段链路，避免在一个会话里硬切身份导致定位漂移。

登录编排      → login_page.login_as(env, "pm01")      （pages/login_page.py）
取行标题/状态 → task_board_page.get_row_title/wait_task_status（pages/task_board_page.py）
任务清理      → task_cleaner fixture 登记，teardown 统一删（conftest.py）
用例里只留业务断言。全程显式等待，不使用 time.sleep。
"""
from __future__ import annotations

import uuid

import allure
import pytest

pytestmark = pytest.mark.ui

# 新建任务弹窗「指派给」下拉的显示文本。
# 前端 label 拼的是 `${realName} (${roleLabel(role)})`，roleLabel('DEV') = '开发'，
# 已实测精确命中，不用改。
ASSIGNEE_DISPLAY = "张开发 (开发)"

# 前端 ElMessage 原文（src/views/task/TaskBoard.vue）
MSG_CREATED = "任务已创建"
MSG_ACCEPTED = "已接受任务，开始处理吧"


@allure.feature("任务看板")
class TestTaskBoardFlow:
    """看板流转：PM 建单 → DEV 接受。"""

    # ------------------------------------------------------------------
    @allure.story("新建任务")
    @allure.title("PM 在看板新建任务，提示成功且表格出现该任务")
    def test_create_task_appears_on_board(
            self, env, login_page, task_board_page, project_id, task_cleaner
    ):
        # 交给 fixture 登记：用例中途失败也会删，不用自己写 try/finally
        title = task_cleaner(f"UI-建单-{uuid.uuid4().hex[:8]}", project_id)

        with allure.step("PM 登录并进入任务看板"):
            login_page.login_as(env, "pm01")
            task_board_page.open(project_id)
            assert not task_board_page.is_readonly(), "项目处于只读状态，PM 无法新建任务"

        with allure.step("点击「新建任务」，填写标题并选择指派给"):
            task_board_page.open_create_dialog()
            task_board_page.fill_create_form(title, ASSIGNEE_DISPLAY)
            task_board_page.submit_create()

        # 提示是 toast，会被下一条用例的登录清掉，所以先断言它
        with allure.step("断言全局提示「任务已创建」"):
            task_board_page.wait_message(MSG_CREATED)

        with allure.step("断言表格中出现该任务标题"):
            text = task_board_page.get_row_title(title)
            print(f"[TASK] 新建后行标题 = {text!r}")
            assert text == title, f"行标题不对：{text!r}，期望 {title!r}"

    # ------------------------------------------------------------------
    @allure.story("接受任务")
    @allure.title("DEV 在详情抽屉接受任务，提示成功且状态变为「进行中」")
    def test_accept_task_updates_status(
            self, env, db, login_page, task_board_page, project_id, todo_task_id
    ):
        task_row = db.fetch_task(todo_task_id)
        assert task_row, f"DB 中不存在任务 {todo_task_id}"
        title = task_row["title"]
        print(f"[TASK] 预置任务 {todo_task_id}「{title}」 DB status={task_row.get('status')!r}")

        # 这条用例的任务由 todo_task_id fixture 自己删，不再登记到 task_cleaner，
        # 否则会重复删、打一条 404「任务不存在」的噪音告警。
        with allure.step("DEV 登录并进入任务看板"):
            login_page.login_as(env, "dev01")
            task_board_page.open(project_id)

        with allure.step("在表格中找到该任务并打开详情抽屉"):
            task_board_page.get_row_title(title)
            task_board_page.click_task_title(title)
            # 有可执行动作时 drawerHint 为空、span 不渲染，这里只是打日志
            print(f"[TASK] 抽屉提示 = {task_board_page.get_drawer_hint()!r}（空表示有可用动作）")

        with allure.step("点击「接受任务」并断言提示"):
            task_board_page.click_drawer_action("接受任务")
            # 原文是「已接受任务，开始处理吧」，逐字对上才算通过
            task_board_page.wait_message(MSG_ACCEPTED)
            print("[TASK] toast 已出现：", MSG_ACCEPTED)

        with allure.step("关闭抽屉，回到列表"):
            task_board_page.close_drawer()

        with allure.step("断言列表状态标签变为「进行中」"):
            status = task_board_page.wait_task_status(title, "进行中")
            print(f"[TASK] 列表状态 = {status!r}")
            assert status == "进行中", f"接受后列表状态应为「进行中」，实际 {status!r}"

        with allure.step("DB 双重断言：任务状态已落库为 DOING"):
            task_after = db.fetch_task(todo_task_id)
            assert task_after, f"DB 中找不到任务 {todo_task_id}"
            print(f"[TASK] DB status = {task_after.get('status')!r}")
            assert task_after["status"] == "DOING", \
                f"落库状态应为 DOING，实际 {task_after.get('status')!r}"
