"""任务看板核心流转 UI 用例。

产品规则决定了这条链路天然横跨两个身份：新建任务只对 ADMIN / PM 开放，
接受任务只有负责人本人（isAssignee）能操作。所以拆成两条用例各自聚焦一段，
避免在一个会话里硬切身份导致定位漂移。

全程显式等待（utils/waits.py），不使用 time.sleep；用例失败由根目录 conftest 的
pytest_runtest_makereport 自动截图并挂到 Allure。
"""

from __future__ import annotations

import uuid

import allure
import pytest

pytestmark = pytest.mark.ui


def _delete_task(task_api, token: str, title: str, project_id: int) -> None:
    """清理 UI 造出的任务。查不到就当已删除，不掩盖用例本身的失败。"""
    try:
        task_id = task_api.find_id_by_title(token, title, project_id)
    except Exception:
        return
    task_api.delete(token, task_id)


@allure.feature("任务看板")
@allure.story("新建任务")
class TestCreateTaskOnBoard:
    @allure.title("PM 在看板新建任务，提示成功且表格出现该任务")
    def test_create_task_appears_on_board(
        self, env, login_page, task_board_page, project_id, task_api, pm_token
    ):
        title = f"UI-建单-{uuid.uuid4().hex[:8]}"

        with allure.step("PM 登录并进入任务看板"):
            account = env["accounts"]["pm01"]
            login_page.open()
            login_page.login(account["username"], str(account["password"]))
            login_page.wait_until_logged_in()
            task_board_page.open(project_id)

        try:
            with allure.step("点击「新建任务」，填写标题并选择负责人"):
                task_board_page.open_create_dialog()
                task_board_page.fill_create_form(title)
                task_board_page.submit_create()

            with allure.step("断言全局提示「任务已创建」"):
                task_board_page.wait_message("任务已创建")

            with allure.step("断言表格中出现该任务标题"):
                assert task_board_page.wait_row(title).text.strip() == title
        finally:
            _delete_task(task_api, pm_token, title, project_id)


@allure.feature("任务看板")
@allure.story("接受任务")
class TestAcceptTaskFromDrawer:
    @allure.title("DEV 在详情抽屉接受任务，提示成功且状态变为「进行中」")
    def test_accept_task_updates_status(
        self, env, db, login_page, task_board_page, project_id, todo_task_id
    ):
        task_row = db.fetch_task(todo_task_id)
        assert task_row, f"DB 中不存在任务 {todo_task_id}"
        title = task_row["title"]

        with allure.step("DEV 登录并进入任务看板"):
            account = env["accounts"]["dev01"]
            login_page.open()
            login_page.login(account["username"], str(account["password"]))
            login_page.wait_until_logged_in()
            task_board_page.open(project_id)

        with allure.step("在表格中找到该任务并打开详情抽屉"):
            task_board_page.wait_row(title)
            task_board_page.open_detail(title)

        with allure.step("点击「接受任务」并断言提示"):
            task_board_page.accept_task()
            task_board_page.wait_message("已接受任务")

        with allure.step("断言列表状态标签变为「进行中」"):
            assert task_board_page.row_status(title) == "进行中"

        with allure.step("DB 双重断言：任务状态已落库为 DOING"):
            assert db.fetch_task(todo_task_id)["status"] == "DOING"
