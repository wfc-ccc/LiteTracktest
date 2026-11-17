"""全局夹具：HTTP 会话、多角色 Token、项目自动创建&清理、任务造数、Chrome 驱动、失败截图。"""
from __future__ import annotations

import uuid
import allure
import pytest
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from api.auth_api import AuthApi
from api.task_api import TaskApi
from api.project_api import ProjectApi
from api.bug_api import BugApi
from api.user_api import UserApi
from api.notification_api import NotificationApi
from api.stats_api import StatsApi
from api.task_block_api import TaskBlockApi

from pages.login_page import LoginPage
from pages.task_board_page import TaskBoardPage
from pages.components.sidebar_page import SidebarPage
from pages.components.notice_center import NoticeCenterComponent

from utils.config_loader import ROOT, load_env, load_yaml
from utils.db import DBClient

SCREENSHOT_DIR = ROOT / "screenshots"


class RoleClient(requests.Session):
    """绑定单个角色 Token 的 Session，一个角色一个实例。

    默认头里带上 Authorization，请求路径只写 ``/api/xxx`` 即可，会自动补上 base_url。
    令牌进的是实例私有头，不共用 api_session，避免多角色并行时串号。
    """

    def __init__(self, base_url: str, role: str, account: dict, auth_data: dict):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.role = role
        self.username = account["username"]
        self.token = auth_data["token"]
        self.user = auth_data["user"]
        self.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        })

    def request(self, method, url, *args, **kwargs):
        if not url.startswith(("http://", "https://")):
            url = f"{self.base_url}/{url.lstrip('/')}"
        return super().request(method, url, *args, **kwargs)


def pytest_addoption(parser):
    parser.addoption(
        "--headless",
        action="store_true",
        default=False,
        help="以 Chrome Headless 运行 UI 用例（Jenkins 必须打开）",
    )


@pytest.fixture(scope="session")
def env():
    """当前环境。读取方式见 utils.config_loader.load_env。"""
    return load_env()


@pytest.fixture(scope="session")
def api_session():
    """进程内复用 TCP 连接。Authorization 按请求传递，避免用例之间串号。"""
    session = requests.Session()
    session.headers.update({
        "Accept": "application/json",
        "Content-Type": "application/json",
    })
    yield session
    session.close()


@pytest.fixture(scope="session")
def login(api_session, env):
    """按 env.yaml 的账号键登录，返回 {token, user}，同一账号只登录一次。"""
    auth_api = AuthApi(api_session, env["api_base_url"])
    cache: dict[str, dict] = {}

    def _login(account_key: str) -> dict:
        if account_key not in cache:
            account = env["accounts"][account_key]
            cache[account_key] = auth_api.login(account["username"], str(account["password"]))
        return cache[account_key]

    return _login


# --- 统一暴露 Token 供断言使用 ---
@pytest.fixture(scope="session")
def admin_token(login) -> str:
    return login("admin")["token"]


@pytest.fixture(scope="session")
def pm_token(login) -> str:
    return login("pm01")["token"]


@pytest.fixture(scope="session")
def dev_token(login) -> str:
    return login("dev01")["token"]


@pytest.fixture(scope="session")
def qa_token(login) -> str:
    return login("qa01")["token"]


@pytest.fixture(scope="session")
def role_client_factory(env, login):
    """按账号键构造 RoleClient，会话结束时统一关闭。"""
    created: list[RoleClient] = []

    def _make(account_key: str) -> RoleClient:
        client = RoleClient(env["api_base_url"], account_key, env["accounts"][account_key], login(account_key))
        created.append(client)
        return client

    yield _make

    for client in created:
        client.close()


@pytest.fixture(scope="session")
def admin_client(role_client_factory) -> RoleClient:
    return role_client_factory("admin")


@pytest.fixture(scope="session")
def pm_client(role_client_factory) -> RoleClient:
    return role_client_factory("pm01")


@pytest.fixture(scope="session")
def dev_client(role_client_factory) -> RoleClient:
    return role_client_factory("dev01")


@pytest.fixture(scope="session")
def qa_client(role_client_factory) -> RoleClient:
    return role_client_factory("qa01")


@pytest.fixture(scope="session")
def db(env) -> DBClient:
    """数据库只读查询入口，用于接口响应与真实落库的双重断言。"""
    return DBClient.from_env(env)


# ================= 核心改造：基于 RoleClient 构建全量 API 实例 =================
# 这里遵循：哪个角色能调哪个接口，就给它配对应的 API 实例。

# --- 任务 API ---
@pytest.fixture(scope="session")
def task_api(api_session, env) -> TaskApi:
    """匿名任务 API，用于测试未登录拦截"""
    return TaskApi(api_session, env["api_base_url"])


@pytest.fixture(scope="session")
def pm_task_api(pm_client) -> TaskApi:
    return TaskApi(pm_client, base_url="")


@pytest.fixture(scope="session")
def dev_task_api(dev_client) -> TaskApi:
    return TaskApi(dev_client, base_url="")


@pytest.fixture(scope="session")
def admin_task_api(admin_client) -> TaskApi:
    return TaskApi(admin_client, base_url="")


# --- 缺陷 API ---
@pytest.fixture(scope="session")
def qa_bug_api(qa_client) -> BugApi:
    return BugApi(qa_client, base_url="")


@pytest.fixture(scope="session")
def dev_bug_api(dev_client) -> BugApi:
    return BugApi(dev_client, base_url="")


# --- 其他模块 API ---
@pytest.fixture(scope="session")
def pm_project_api(pm_client) -> ProjectApi:
    return ProjectApi(pm_client, base_url="")


@pytest.fixture(scope="session")
def admin_user_api(admin_client) -> UserApi:
    return UserApi(admin_client, base_url="")


@pytest.fixture(scope="session")
def pm_notification_api(pm_client) -> NotificationApi:
    return NotificationApi(pm_client, base_url="")


@pytest.fixture(scope="session")
def pm_stats_api(pm_client) -> StatsApi:
    return StatsApi(pm_client, base_url="")


@pytest.fixture(scope="session")
def dev_task_block_api(dev_client) -> TaskBlockApi:
    return TaskBlockApi(dev_client, base_url="")


# ====================== 改造点：创建项目时直接传入 memberIds ======================
@pytest.fixture(scope="session", autouse=True)
def auto_create_project(pm_client, env, login):
    """env 未配置 project_id 时，由 pm01 自动创建测试项目，并在创建时把 dev01、qa01 加入成员。"""
    if env.get("project_id"):
        yield None
        return

    base_url = env["api_base_url"]
    proj_create_url = f"{base_url}/api/projects"
    proj_list_url = f"{base_url}/api/projects"
    proj_id = None
    proj_name = f"pytest-auto-proj-{uuid.uuid4().hex[:12]}"

    try:
        dev_uid = login("dev01")["user"]["id"]
        qa_uid = login("qa01")["user"]["id"]
        member_ids = [dev_uid, qa_uid]
        print(f"[debug] memberIds={member_ids}")

        # 1. PM 创建项目，并通过 ProjectSaveDTO.memberIds 直接加入成员
        resp = pm_client.post(proj_create_url, json={
            "name": proj_name,
            "description": "自动创建，会话结束自动清理",
            "memberIds": member_ids
        }, timeout=10)
        body = resp.json()
        assert body.get("code") == 200, f"创建项目失败：{body}"

        # 2. 创建接口返回 Void，按名称回查列表获取项目 id
        resp_list = pm_client.get(proj_list_url, params={
            "name": proj_name,
            "current": 1,
            "size": 10
        }, timeout=10)
        list_body = resp_list.json()
        records = (list_body.get("data") or {}).get("records") or []
        assert records, f"未查询到刚创建的项目：{proj_name}"

        proj_id = int(records[0]["id"])
        env["project_id"] = proj_id
        print(f"[init project] 创建项目成功，name={proj_name}, id={proj_id}, memberIds={member_ids}")

        yield proj_id

    finally:
        # 3. 会话结束自动删除项目
        if proj_id:
            try:
                pm_client.delete(f"{base_url}/api/projects/{proj_id}", timeout=10)
                print(f"[clean project] 删除项目成功，id={proj_id}")
            except Exception as e:
                print(f"[clean project] 删除项目失败，id={proj_id}：{e}")


# ================= 造数逻辑改造：强化清理容错 =================

@pytest.fixture(scope="session")
def audit_payload() -> dict:
    return load_yaml("task_audit.yaml")


@pytest.fixture(scope="session")
def project_id(pm_client, env) -> int:
    """造数项目 ID：env.yaml 配了就用，否则取 PM 可见的第一个项目。"""
    return _resolve_project_id(pm_client, env)


def _resolve_project_id(client: requests.Session, env: dict) -> int:
    configured = env.get("project_id")
    if configured:
        return int(configured)

    response = client.get("/api/projects", params={"current": 1, "size": 1}, timeout=15)
    body = response.json()
    records = (body.get("data") or {}).get("records") or []
    if body.get("code") != 200 or not records:
        pytest.fail("env.yaml 未配置 project_id，且 PM 账号下没有可用项目。请先建项目或写上 project_id。")
    return int(records[0]["id"])


@pytest.fixture
def todo_task_id(pm_task_api, pm_client, login, env) -> int:
    """PM 创建一条指派给 DEV 的任务并交出 task_id，用例结束后删除。"""
    project_id = _resolve_project_id(pm_client, env)
    assignee_id = login("dev01")["user"]["id"]
    title = f"auto-todo-{uuid.uuid4().hex[:12]}"

    pm_task_api.create({
        "projectId": project_id,
        "title": title,
        "description": "状态机/权限矩阵造数，用例结束会删除",
        "priority": "LOW",
        "assigneeId": assignee_id,
    })

    task_id = pm_task_api.find_id_by_title(title, project_id)

    yield task_id

    try:
        pm_task_api.delete(task_id)
    except Exception as e:
        print(f"\n[Teardown Warning] 清理任务 {task_id} 失败: {e}")


@pytest.fixture
def setup_task(pm_task_api, pm_client, login, env, audit_payload) -> int:
    """PM 创建一条任务，推进到待审核后交出 task_id，用例结束后删除。"""
    project_id = _resolve_project_id(pm_client, env)
    assignee_id = login("dev01")["user"]["id"]
    title = f"auto-audit-{uuid.uuid4().hex[:12]}"

    pm_task_api.create({
        "projectId": project_id,
        "title": title,
        "description": "权限矩阵临时任务，用例结束会删除",
        "priority": "LOW",
        "assigneeId": assignee_id,
    })

    task_id = pm_task_api.find_id_by_title(title, project_id)
    pm_task_api.accept(task_id)
    pm_task_api.submit(task_id, audit_payload["submit"])

    yield task_id

    try:
        pm_task_api.delete(task_id)
    except Exception as e:
        print(f"\n[Teardown Warning] 清理任务 {task_id} 失败: {e}")


# ================= UI 自动化 Fixture =================

@pytest.fixture
def driver(request):
    """每个 UI 用例一个 Chrome。--headless 时使用无头模式，结束时 quit。"""
    options = Options()
    if request.config.getoption("--headless"):
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,900")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    browser = webdriver.Chrome(options=options)
    browser.set_page_load_timeout(30)
    yield browser
    browser.quit()


@pytest.fixture
def logged_in_driver(driver, env, login, pm_token):
    """
    利用 API 拿到 Token 后，直接通过 JS 注入浏览器的 localStorage，跳过 UI 登录步骤。
    默认使用 PM 角色，如果想用其他角色，在用例中重新注入即可。
    """
    driver.get(env["web_base_url"])
    driver.execute_script(f"window.localStorage.setItem('litetrack_token', '{pm_token}')")
    driver.get(f"{env['web_base_url']}/dashboard")

    from utils.waits import wait_for_element_visible
    from selenium.webdriver.common.by import By
    wait_for_element_visible(driver, (By.CSS_SELECTOR, ".navbar__title"))
    return driver


@pytest.fixture
def login_page(driver, env) -> LoginPage:
    return LoginPage(driver, env["web_base_url"])


@pytest.fixture
def task_board_page(logged_in_driver, env) -> TaskBoardPage:
    """使用已登录的 driver 初始化任务看板"""
    return TaskBoardPage(logged_in_driver, env["web_base_url"])


@pytest.fixture
def sidebar(logged_in_driver, env) -> SidebarPage:
    return SidebarPage(logged_in_driver, env["web_base_url"])


@pytest.fixture
def notice_center(logged_in_driver, env) -> NoticeCenterComponent:
    return NoticeCenterComponent(logged_in_driver, env["web_base_url"])


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    """用例失败且 driver 仍存活时截图，附加到 Allure。此时尚未执行 fixture teardown。"""
    outcome = yield
    report = outcome.get_result()
    if report.when not in ("setup", "call") or not report.failed:
        return

    browser = item.funcargs.get("driver")
    if browser is None:
        return

    try:
        png = browser.get_screenshot_as_png()
    except Exception:
        return

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    file_path = SCREENSHOT_DIR / f"{item.name}.png"
    file_path.write_bytes(png)
    allure.attach(png, name=f"失败截图-{item.name}", attachment_type=allure.attachment_type.PNG)
