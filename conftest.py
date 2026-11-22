"""全局夹具：HTTP 会话、多角色 Token、项目自动创建&清理、任务造数、Chrome/Edge 驱动、失败截图。"""
from __future__ import annotations

import uuid

import allure
import pytest
import requests

from api.auth_api import AuthApi
from api.task_api import TaskApi
from api.project_api import ProjectApi
from api.bug_api import BugApi
from api.user_api import UserApi
from api.notification_api import NotificationApi
from api.stats_api import StatsApi
from api.task_block_api import TaskBlockApi

from selenium.webdriver.common.by import By

from pages.login_page import LoginPage
from pages.task_board_page import TaskBoardPage
from pages.components.sidebar_page import SidebarPage
from pages.components.notice_center import NoticeCenterComponent

from utils.config_loader import ROOT, load_env, load_yaml
from utils.db import DBClient
from utils.waits import wait_for_element_visible

SCREENSHOT_DIR = ROOT / "screenshots"


class RoleClient(requests.Session):
    """绑定单个角色 Token 的 Session，一个角色一个实例。

    只带 Authorization，请求路径只写 ``/api/xxx`` 即可，会自动补上 base_url。
    令牌进的是实例私有头，不共用 api_session，避免多角色并行时串号。

    **不要在这里设置 Accept / Content-Type**，两个都会踩坑：
      · 会话级 Content-Type 会覆盖 requests 按 files= 自动生成的 multipart 头，
        请求体带着 application/json 出去，后端直接抛
        MultipartException: Current request is not a multipart request，
        表现为「浏览器能上传、脚本传就 400/500」；
      · 会话级 Accept: application/json 会让 /api/ai/chat（produces=text/event-stream）
        在 handler 匹配阶段就抛 HttpMediaTypeNotAcceptableException，方法体都进不去。
    不写这两个头时，requests 会按场景自动补：json= → application/json，
    files= → multipart/form-data; boundary=...，Accept 缺省 */*，SSE 与 JSON 都接受。
    """

    def __init__(self, base_url: str, role: str, account: dict, auth_data: dict):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.role = role
        self.username = account["username"]
        self.token = auth_data["token"]
        self.user = auth_data["user"]
        self.headers.update({
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
        help="以无头模式运行 UI 用例（Jenkins 必须打开）",
    )


@pytest.fixture(scope="session")
def env():
    """当前环境。读取方式见 utils.config_loader.load_env。"""
    return load_env()


@pytest.fixture(scope="session")
def api_session():
    """进程内复用 TCP 连接。Authorization 按请求传递，避免用例之间串号。

    不设 Accept / Content-Type：理由同 RoleClient —— 会话级 Content-Type 会破坏
    multipart，会话级 Accept: application/json 会挡住 SSE 接口。
    """
    session = requests.Session()
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


@pytest.fixture(scope="session")
def no_auth_client(env) -> requests.Session:
    """无token匿名会话，用于未登录鉴权测试

    同样不设 Accept / Content-Type：匿名上传用例要发的是 multipart，
    会话级 Content-Type 同样会把它打坏（后端报 not a multipart request）。
    """
    sess = requests.Session()
    sess.base_url = env["api_base_url"].rstrip("/")
    yield sess
    sess.close()


# ====================== 项目单例：整个 session 最多创建 1 次 ======================
# 用模块级字典而不是 fixture 缓存，是因为 _resolve_project_id 是普通函数，
# 无法请求 fixture；这样无论谁先要项目，都只会走到同一个 id。
_PROJECT: dict = {"id": None, "name": None, "owned": False}


def _ensure_project(pm_client, env, login) -> int:
    """取项目 ID，没有就**创建恰好一次**，之后全进程复用同一个 id。

    优先级：_PROJECT 缓存 → env.yaml 的 project_id → 新建一个带 DEV/QA 成员的项目。
    """
    if _PROJECT["id"]:
        return int(_PROJECT["id"])

    base_url = env["api_base_url"]

    # 1) env.yaml 配了项目，直接复用，只补一下项目名
    if env.get("project_id"):
        proj_id = int(env["project_id"])
        _PROJECT.update({"id": proj_id, "name": env.get("project_name"), "owned": False})
        if not env.get("project_name"):
            try:
                body = pm_client.get(f"{base_url}/api/projects/{proj_id}", timeout=10).json()
                if body.get("code") == 200 and body.get("data"):
                    env["project_name"] = body["data"]["name"]
            except Exception as e:
                print(f"\n[init project] ⚠️ 查询项目名失败：{type(e).__name__}: {e}")
        print(f"\n[init project] 复用 env.yaml 配置的项目：id={proj_id}, name={env.get('project_name')}")
        return proj_id

    # 2) 没有配置才新建，且只建这一次
    proj_name = f"pytest-auto-proj-{uuid.uuid4().hex[:12]}"
    resp = pm_client.post(f"{base_url}/api/projects", json={
        "name": proj_name,
        "description": "自动创建，会话结束自动清理",
        "memberIds": [login("dev01")["user"]["id"], login("qa01")["user"]["id"]],
    }, timeout=10)
    assert resp.json().get("code") == 200, f"创建项目失败：{resp.text}"

    records = (
        pm_client.get(f"{base_url}/api/projects",
                      params={"name": proj_name, "current": 1, "size": 10}, timeout=10)
        .json().get("data") or {}
    ).get("records") or []
    assert records, f"未查询到刚创建的项目：{proj_name}"

    proj_id = int(records[0]["id"])
    _PROJECT.update({"id": proj_id, "name": proj_name, "owned": True})
    env["project_id"] = proj_id
    env["project_name"] = proj_name
    print(f"\n[init project] 本次运行首次创建项目：id={proj_id}, name={proj_name}（后续用例全部复用，不再新建）")
    return proj_id


@pytest.fixture(scope="session", autouse=True)
def auto_create_project(pm_client, env, login):
    """Session 级前置，但**自己不建项目**。

    以前这一版是无条件在 session 开头新建项目，于是「跑一条 UI 用例也会多建一个项目」。
    现在它只做两件事：env.yaml 配了 project_id 就校验并补项目名；没配就什么都不做。
    真正需要项目的是 project_id / todo_task_id / setup_task / task_cleaner 这几个夹具，
    它们调用 _ensure_project，整个进程最多建 1 个，teardown 只删自己建的那个。
    不碰项目的用例（AI 助手、登录、通知等）一条都不会建。
    """
    base_url = env["api_base_url"]

    if env.get("project_id"):
        _ensure_project(pm_client, env, login)
    else:
        print("\n[init project] env.yaml 未配置 project_id：本次不预建项目，谁需要谁触发（最多 1 个）")

    yield _PROJECT["id"]

    if _PROJECT["owned"] and _PROJECT["id"]:
        try:
            pm_client.delete(f"{base_url}/api/projects/{_PROJECT['id']}", timeout=10)
            print(f"\n[clean project] 已删除本次运行创建的项目：id={_PROJECT['id']}")
        except Exception as e:
            print(f"\n[clean project] ⚠️ 删除项目 id={_PROJECT['id']} 失败：{type(e).__name__}: {e}")


# ================= 造数逻辑改造：强化清理容错 =================

@pytest.fixture(scope="session")
def audit_payload() -> dict:
    return load_yaml("task_audit.yaml")


@pytest.fixture(scope="session")
def project_id(pm_client, env, login) -> int:
    """造数项目 ID：整个 session 单例，最多创建 1 次（见 _ensure_project）。"""
    return _ensure_project(pm_client, env, login)


def _resolve_project_id(client: requests.Session, env: dict, login) -> int:
    """兼容旧调用点的薄封装，同样走单例，不会重复建项目。"""
    return _ensure_project(client, env, login)


@pytest.fixture
def todo_task_id(pm_task_api, pm_client, login, env, project_id) -> int:
    """PM 创建一条指派给 DEV 的任务并交出 task_id，用例结束后删除。"""
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
def setup_task(pm_task_api, pm_client, login, env, audit_payload, project_id) -> int:
    """PM 创建一条任务，推进到待审核后交出 task_id，用例结束后删除。"""
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


# ================= UI 造数清理：登记式 =================

def _delete_one_task(client, title: str, project_id: int) -> None:
    """按标题查 ID 再删。查不到就当已删除；删除失败只告警，不掩盖用例本身的失败。"""
    try:
        task_id = client.find_id_by_title(title, project_id)
    except Exception as e:
        print(f"[TASK-CLEANUP] 查不到任务「{title}」，视为已删除（{type(e).__name__}）")
        return

    try:
        client.delete(task_id)
        print(f"[TASK-CLEANUP] ✅ 已删除任务 {task_id}（{title}）")
    except Exception as e:
        print(f"[TASK-CLEANUP] ⚠️ 删除任务 {task_id} 失败：{type(e).__name__}: {e}")


@pytest.fixture
def task_cleaner(pm_task_api, pm_client, env, login):
    """登记式任务清理，供 UI 用例造数后使用。

    用例把标题交给它即可，teardown 统一按标题查 ID 再删：

        title = task_cleaner(f"UI-建单-{uuid.uuid4().hex[:8]}", project_id)

    - 用例中途失败也会删（清理跑在 fixture teardown，比正文里的 try/finally 省心）；
    - 已由其他夹具（如 todo_task_id）自己删的任务不要登记，否则会多打一条 404 告警；
    - 函数级 teardown 早于 session 级的 auto_create_project 删项目，
      所以不会出现「项目没了才去删任务」；
    - 不传 project_id 时取的是 session 单例项目，不会为了清理再建项目。
    """
    registered: list[tuple[str, int]] = []

    def _register(title: str, project_id: int | None = None) -> str:
        pid = int(project_id) if project_id else _resolve_project_id(pm_client, env, login)
        registered.append((title, pid))
        return title

    yield _register

    for title, pid in registered:
        _delete_one_task(pm_task_api, title, pid)


# ================= UI 自动化 Fixture =================

@pytest.fixture
def driver(request, env, pm_client, login):
    """每个 UI 用例一个 Edge。--headless 时使用无头模式，结束时 quit。

    顺带保证「项目就绪」：不少既有 UI 用例直接用 env["project_id"]
    （如 test_ui_bug_lifecycle 里的 bug_list_page.open(env["project_id"])），
    不经过 project_id 夹具，所以在这里触发一次 _ensure_project。
    一个 session 只会建一次（内部有缓存），第二条用例起直接命中缓存。
    """
    from selenium.webdriver.edge.options import Options
    from selenium.webdriver import Edge

    options = Options()
    if request.config.getoption("--headless"):
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,900")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    _ensure_project(pm_client, env, login)  # 放在起浏览器之前，失败时不必白开一个窗口

    browser = Edge(options=options)
    browser.set_page_load_timeout(30)
    yield browser
    browser.quit()


@pytest.fixture
def logged_in_driver(driver, env):
    """真实账号密码登录（默认 pm01，可用 env.yaml 的 ui_role 覆盖），落在 /dashboard。

    以前是「API 拿 token → JS 注入 localStorage」，快但有两个硬伤：
      1. 只注了 token、没注 userStore，userStore.role 为空，
         canManage / isAdmin 一律 False，按角色判按钮可见性的用例会假阴性；
      2. 绕过了登录页，登录页自身的校验、跳转、token 落库都没被覆盖过。
    现在走 LoginPage.login_as：清 localStorage → /login → 输账号密码 → 断言进了 /dashboard，
    失败时会带当前 URL 和页面 toast 一起报出来。
    """
    role = str(env.get("ui_role") or "pm01")
    LoginPage(driver, env["web_base_url"]).login_as(env, role)
    wait_for_element_visible(driver, (By.CSS_SELECTOR, ".navbar__title"))
    return driver


@pytest.fixture
def switch_role(driver, env):
    """真实账号密码切换角色：登出当前账号，再用目标账号完整登录一遍。

    返回切换后的 URL，方便用例断言确实换了人。
    LoginPage.login_as 内部会先清 localStorage/Cookie 再打开 /login，
    所以不需要单独调 logout。
    """
    def _switch(account_key: str) -> str:
        LoginPage(driver, env["web_base_url"]).login_as(env, account_key)
        return driver.current_url

    return _switch


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
