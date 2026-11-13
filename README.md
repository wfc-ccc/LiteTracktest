# LiteTrack 自动化测试框架

> 轻舟 LiteTrack —— 轻量级敏捷项目协作与缺陷跟踪系统的接口 / Web UI 自动化测试工程。

[![pytest](https://img.shields.io/badge/pytest-8.x-0A9EDC?logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Selenium](https://img.shields.io/badge/Selenium-4.x-43B02A?logo=selenium&logoColor=white)](https://www.selenium.dev/)
[![Allure](https://img.shields.io/badge/Report-Allure-FF6F00)](https://allurereport.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](#license)

用 pytest 分层组织接口与 UI 两条测试线，覆盖 LiteTrack 的**状态机流转**、**多角色权限隔离**、**参数边界校验**与**前后端联调**，并接入 Allure 报告与 Jenkins 流水线。

---

## 目录

- [项目简介](#项目简介)
- [特性亮点](#特性亮点)
- [测试架构](#测试架构)
- [技术栈](#技术栈)
- [目录结构](#目录结构)
- [快速开始](#快速开始)
- [用例清单](#用例清单)
- [核心设计](#核心设计)
- [配置说明](#配置说明)
- [运行与报告](#运行与报告)
- [持续集成](#持续集成)
- [常见问题](#常见问题)
- [参与贡献](#参与贡献)
- [License](#license)

---

## 项目简介

LiteTrack 是前后端分离的敏捷协作系统：前端 **Vue 3 + Element Plus**，后端 **Spring Boot**。本仓库是它的自动化测试工程，独立于业务代码仓库，通过 HTTP 与浏览器两条通道对被测系统做黑盒验证。

被测系统的一条重要契约：后端统一响应体为 `Result<T>`，结构是 `{ code, message, data }`。**全局异常处理器不改写 HTTP 状态码**，所以无权限、非法状态流转这类业务失败，常见结果是 **HTTP 200，但 `code` 为 403 / 业务码**。

本框架的所有断言都对齐这条契约，而不是只看 HTTP 状态码。

---

## 特性亮点

- **双重断言**：接口响应与数据库直连（MySQL）互为印证，既验「接口说成功」，也验「数据真落库」。

- **零副作用断言**：越权、非法状态流转等被拦截的请求，会比对拦截前后的字段快照，确保数据库未产生脏数据。

- **权限矩阵数据驱动**：角色 × 接口的对应关系外置到 `data/permission_matrix.yaml`，改规则只改 YAML，不动用例代码。

- **状态机防篡改**：逆向对 DONE / TODO 状态发送非法流转请求，验证后端状态机拦截生效。

- **POM 页面对象模式**：定位器基于真实前端源码（`.login__title`、`.task-title-link` 等），页面元素与用例逻辑解耦。

- **全程显式等待**：所有 UI 等待统一走 `utils/waits.py` 的 `WebDriverWait` 封装，**禁止 `time.sleep()`**。

- **失败自动截图**：`pytest_runtest_makereport` 钩子在浏览器关闭前抓图，并作为 PNG 挂载到 Allure 对应用例。

- **多角色会话隔离**：`RoleClient`（`requests.Session` 子类）按角色持有各自的 Token，避免并行执行时串号。

---

## 测试架构

```text
                 ┌──────────────────────────────────────┐
                 │           testcases/                 │
                 │   api/  ──▶ 接口自动化（秒级）        │
                 │   ui/   ──▶ Web UI 自动化（浏览器）    │
                 └───────────────┬──────────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                        ▼
 ┌─────────────┐         ┌─────────────┐          ┌─────────────┐
 │  api/       │         │  pages/     │          │  utils/     │
 │  接口封装    │         │  POM 页面对象│          │  等待/配置/DB│
 └─────────────┘         └─────────────┘          └─────────────┘
        │                        │                        │
        └────────────────────────┼────────────────────────┘
                                 ▼
                    ┌──────────────────────────┐
                    │        conftest.py       │
                    │  Session / Token / 造数   │
                    │  Chrome / 失败截图 夹具   │
                    └──────────────────────────┘
```

**分层职责**

| 层次 | 目录 | 职责 |
| --- | --- | --- |
| 用例层 | `testcases/` | 只写业务断言与步骤，不含定位器与 HTTP 细节 |
| 接口层 | `api/` | 一个资源一个类，封装请求与响应解析 |
| 页面层 | `pages/` | 页面对象，封装定位器与操作 |
| 工具层 | `utils/` | 显式等待、配置读取、数据库直连 |
| 夹具层 | `conftest.py` | 会话、Token、造数、浏览器、失败截图 |

---

## 技术栈

| 分类 | 选型 |
| --- | --- |
| 用例框架 | pytest 8、pytest-xdist |
| 接口测试 | requests（`Session` 子类做角色隔离） |
| UI 测试 | Selenium 4（显式等待 + 页面对象） |
| 数据断言 | PyMySQL（DictCursor） |
| 报告 | allure-pytest |
| 配置与数据 | PyYAML |
| 流水线 | Jenkins 声明式 Pipeline |
| 运行环境 | Python 3.10+、Chrome（Selenium 4.11+ 自带驱动管理） |

---

## 目录结构

```text
litetracktest/
├── api/                              # 接口封装，一个资源一个类
│   ├── auth_api.py                   # POST /api/auth/login，取出 token 与 user
│   └── task_api.py                   # 任务：创建 / 查询 / 接受 / 提交 / 审核 / 删除
├── pages/                            # 页面对象（POM）
│   ├── base_page.py                  # 打开页面、显式等待、输入、点击
│   ├── login_page.py                 # src/views/Login.vue
│   └── task_board_page.py            # src/views/task/TaskBoard.vue
├── testcases/
│   ├── api/
│   │   ├── test_task_lifecycle.py    # 任务全生命周期（含工时去空格容错）
│   │   ├── test_bug_lifecycle.py     # 缺陷闭环 + 七项打回参数校验
│   │   ├── test_task_state_machine.py# 状态机逆向拦截
│   │   ├── test_task_validation.py   # submitHours 等参数边界
│   │   ├── test_permission_matrix.py # 4 角色 × 3 敏感接口（YAML 驱动）
│   │   └── test_task_permission.py   # 审核接口角色断言
│   └── ui/
│       ├── test_login_flow.py        # 登录跳转 /dashboard
│       └── test_ui_task_flow.py      # 新建任务、接受任务
├── utils/
│   ├── config_loader.py              # 读取 env.yaml 与 data/*.yaml
│   ├── db.py                         # PyMySQL 封装，双重断言用
│   └── waits.py                      # WebDriverWait 封装，禁止 time.sleep
├── config/
│   └── env.yaml                      # 环境地址、测试账号、数据库连接
├── data/
│   ├── permission_matrix.yaml        # 角色 × 接口权限矩阵
│   └── task_audit.yaml               # 提交 / 审核请求体
├── sql/
│   └── seed_test_accounts.sql        # 测试账号与项目造数（幂等）
├── conftest.py                       # 全局夹具与失败截图钩子
├── health_check.py                   # 启动自检：8080 / 5173 存活探测
├── pytest.ini                        # 用例发现与默认参数
├── requirements.txt
├── Jenkinsfile
└── README.md
```

---

## 快速开始

按顺序执行：**后端 → 前端 → 造数 → 自检 → 跑用例**。

### 0. 前置条件

- Python 3.10+、MySQL 8.x、Chrome 浏览器

- 后端仓库（如 `qzsys`）与前端仓库（如 `litetrack-frontend`）已就绪

- 安装依赖：

```bash
python -m pip install -r requirements.txt
```

### 1. 启动后端（Spring Boot，:8080）

```bash
# 在【后端仓库】根目录执行
mvn clean package -DskipTests
java -jar target/*.jar
```

看到 `Started LiteTrackApplication` 即就绪。数据库连接串在后端 `application.yml` 中配置。

### 2. 启动前端（Vite，:5173）

```bash
# 在【前端仓库】根目录执行
npm install
npm run dev
```

`vite.config.js` 已把 `/api` 代理到 `http://localhost:8080`，本框架直接访问 5173 即可。

### 3. 造数（初始化测试账号与项目）

```bash
# 在【本仓库】根目录执行
mysql -uroot -p123456 litetrack < sql/seed_test_accounts.sql
```

或直接在 **Navicat** 里打开 `sql/seed_test_accounts.sql` 整段执行。脚本是幂等的，可重复跑。

执行后应能看到 4 个账号（`admin` / `pm01` / `dev01` / `qa01`，口令均为 `123456`）与 1 个造数项目。

> 如果数据库里已有这四个账号，只跑「项目与成员」两段即可（脚本会自动跳过已存在的数据）。

### 4. 自检（探测前后端存活）

```bash
python health_check.py
```

预期输出：

```text
[OK  ] 后端 api  http://localhost:8080  ->  HTTP 200
[OK  ] 前端 web  http://localhost:5173  ->  HTTP 200
环境自检通过（env=dev）
```

任一服务不可用时会打印 `[FAIL]` 并以非 0 退出码结束，适合作为流水线的前置关卡。

### 5. 执行用例

```bash
# 全部用例
pytest testcases -v

# 只跑接口（快）
pytest testcases/api -v

# 只跑 UI（能看到浏览器；无界面环境加 --headless）
pytest testcases/ui -v
pytest testcases/ui -v --headless

# 多进程并行（接口用例）
pytest testcases/api -n auto
```

---

## 用例清单

共 **25** 条用例，其中接口 **22** 条、UI **3** 条。

### 接口用例

| 文件 | 用例 | 验证点 |
| --- | --- | --- |
| `test_task_lifecycle.py` | `test_full_lifecycle` | PM 建单 → DEV 接受 → 提交 → PM 审核通过的完整闭环；`submitHours=" 8.5 "` 验证 `WorkHourDeserializer` 去空格容错 |
| `test_bug_lifecycle.py` | `test_bug_lifecycle` | 缺陷 OPEN → FIXED → CLOSED 闭环 |
| `test_bug_lifecycle.py` | `test_reopen_requires_seven_fields` | 七项必填参数缺失时被拦截，且 DB 状态不变 |
| `test_task_state_machine.py` | `test_accept_on_done_is_rejected` | 对 DONE 任务发 accept，HTTP 200 但业务码非 200，快照不变 |
| `test_task_state_machine.py` | `test_audit_on_todo_is_rejected` | 对 TODO 任务发 audit，被拦截且 `latest_audit_result` 仍为 `None` |
| `test_task_validation.py` | `test_submit_rejects_invalid_params[hours-negative]` | `submitHours=-1` 被拦截，无脏数据 |
| `test_task_validation.py` | `test_submit_rejects_invalid_params[hours-blank]` | `submitHours=""` 被拦截，无脏数据 |
| `test_task_validation.py` | `test_submit_rejects_invalid_params[desc-missing]` | 缺 `submitDesc` 被拦截，无脏数据 |
| `test_permission_matrix.py` | `test_permission_matrix[admin-*]`（3 条） | ADMIN 调 accept / audit / assign 全部放行 |
| `test_permission_matrix.py` | `test_permission_matrix[pm01-*]`（3 条） | PM 同上全部放行 |
| `test_permission_matrix.py` | `test_permission_matrix[dev01-*]`（3 条） | DEV 仅 accept 放行，audit / assign 返回 403 且无副作用 |
| `test_permission_matrix.py` | `test_permission_matrix[qa01-*]`（3 条） | QA 三个接口全部 403 且无副作用 |
| `test_task_permission.py` | `test_audit_permission_matrix[dev-forbidden]` | DEV 调审核接口，`code=403` |
| `test_task_permission.py` | `test_audit_permission_matrix[pm-allowed]` | PM 调审核接口且任务处于待审核，`code=200` |

### UI 用例

| 文件 | 用例 | 验证点 |
| --- | --- | --- |
| `test_login_flow.py` | `test_admin_login_success` | admin / 123456 登录后跳转 `/dashboard`，顶栏展示登录人 |
| `test_ui_task_flow.py` | `test_create_task_appears_on_board` | PM 新建任务：提示「任务已创建」，表格出现该标题 |
| `test_ui_task_flow.py` | `test_accept_task_updates_status` | DEV 接受任务：提示「已接受任务」，状态标签变为「进行中」，DB 落库为 `DOING` |

---

## 核心设计

### 统一响应契约与断言方式

后端 `Result` 结构为 `{ code, message, data }`，全局异常处理器不改写 HTTP 状态。因此：

- **成功**：`HTTP 200` 且 `body.code == 200`

- **业务失败 / 无权限**：`HTTP 200` 且 `body.code == 403` 或其它业务码

用例统一按 `body.code` 断言，而非 HTTP 状态码。

### 双重断言：接口 + 数据库

先用接口拿到业务响应，再用 `utils/db.py` 直连同一条记录核对，两边互为印证：

```python
def test_xxx(task_api, pm_token, db, todo_task_id):
    resp = task_api.accept(pm_token, todo_task_id)
    assert resp.json()["code"] == 200
    assert db.fetch_task(todo_task_id)["status"] == "DOING"
```

### 零副作用断言

越权或非法流转被拦截时，比对拦截前后的字段快照，确保数据库零变更：

```python
before = _snapshot(db, task_id)
resp = dev_client.patch(f"/api/tasks/{task_id}/audit", json={"auditResult": "PASS"})
assert resp.json()["code"] == 403
assert _snapshot(db, task_id) == before      # 一个字段都不能动
```

### 权限矩阵数据驱动

角色与接口的对应关系写在 `data/permission_matrix.yaml`，用例用 `@pytest.mark.parametrize` 笛卡尔积展开：

```yaml
endpoints:
  audit:
    method: PATCH
    path: /api/tasks/{task_id}/audit
    pre_state: PENDING_REVIEW
matrix:
  dev01: { accept: 200, audit: 403, assign: 403 }
  qa01:  { accept: 403, audit: 403, assign: 403 }
```

新增角色或调整规则时，只改 YAML。

### 页面对象与显式等待

定位器基于真实前端源码，页面元素与用例逻辑解耦：

```python
class LoginPage(BasePage):
    TITLE = (By.CSS_SELECTOR, ".login__title")
    SUBMIT = (By.CSS_SELECTOR, "button.login__submit")
```

所有等待统一走 `utils/waits.py`（`WebDriverWait` + `expected_conditions`），**不使用 `time.sleep()`**。Element Plus 的下拉面板常驻 DOM、关闭时仅 `display:none`，因此额外提供了 `wait_for_first_displayed()` 等待「第一个可见项」。

### 失败自动截图

```python
@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    ...
    allure.attach(png, name=f"失败截图-{item.name}", attachment_type=allure.attachment_type.PNG)
```

用例失败且浏览器仍存活时抓图，附加到 Allure 对应用例，无需在用例里写截图代码。

---

## 配置说明

编辑 `config/env.yaml`：

| 键 | 说明 |
| --- | --- |
| `active` | 默认环境名，当前为 `dev` |
| `api_base_url` | 后端根地址，不要带 `/api`（代码会拼） |
| `web_base_url` | 前端根地址 |
| `project_id` | 造数使用的项目。留空时夹具用 PM 账号取项目列表第一条 |
| `task_id` | 复用现成任务时填写，与 `project_id` 二选一 |
| `accounts` | `admin` / `pm01` / `dev01` / `qa01` 的用户名与密码（密码加引号，避免被 YAML 读成数字） |
| `db` | 数据库直连参数，供双重断言使用 |

切换环境不改文件：

```bash
# Windows PowerShell
$env:LITETRACK_ENV = "test"
pytest testcases/api

# Linux / macOS
LITETRACK_ENV=test pytest testcases/api
```

**已封装的夹具**

| 夹具 | 作用 |
| --- | --- |
| `env` | 当前环境字典 |
| `api_session` | 复用的 `requests.Session()` |
| `login` | `login("dev01")` 返回 `{token, user}`，同一账号只登录一次 |
| `admin_token` / `pm_token` / `dev_token` / `qa_token` | 各角色 JWT |
| `admin_client` / `pm_client` / `dev_client` / `qa_client` | 绑定角色 Token 的 `RoleClient`，默认头已带 `Authorization` |
| `db` | `DBClient`，数据库直连，用于双重断言 |
| `todo_task_id` | PM 创建一条指派给 DEV 的 TODO 任务，`yield` 出 `task_id`，结束删除 |
| `setup_task` | PM 创建并推进到待审核状态，`yield` 出 `task_id`，结束删除 |
| `driver` | Chrome；`--headless` 时无头，用例结束 `quit` |
| `login_page` / `task_board_page` | 页面对象 |

Token 请求头格式与后端 `JwtInterceptor` 一致：`Authorization: Bearer <token>`。

---

## 运行与报告

`pytest.ini` 已内置：

```ini
addopts = -v --strict-markers --alluredir=./allure-results --clean-alluredir
```

本地一次执行会先清空 `allure-results`；Jenkins 中接口与 UI 分两次执行并分目录写入，避免互相清理。

查看报告需要 [Allure Commandline](https://allurereport.org/docs/install/)：

```bash
pytest testcases -v
allure serve ./allure-results
```

---

## 持续集成

`Jenkinsfile` 为声明式流水线：

1. **Checkout**：`checkout scm`

2. **Install**：`python -m pip install -r requirements.txt`

3. **Run API Tests**：只跑 `testcases/api`

4. **Run UI Tests**：只跑 `testcases/ui`，并加 `--headless`

5. **Generate Allure Report**：合并两份结果并归档

节点要求：能访问被测环境、已安装 Chrome 与 Allure Commandline。

---

## 常见问题

**Q：登录接口返回 401 / 「用户名或密码错误」？**

数据库缺少 `pm01` / `dev01` / `qa01` 账号。执行 `sql/seed_test_accounts.sql` 补齐即可，口令统一为 `123456`。

**Q：夹具报「PM 账号下没有可用项目」？**

`sql/seed_test_accounts.sql` 会创建造数项目并把 `pm01` 设为 owner。若使用自有项目，把项目 ID 填到 `config/env.yaml` 的 `project_id`。

**Q：接口断言 `code != 200`，但 HTTP 是 200？**

这是后端的正常契约：全局异常处理器不改写 HTTP 状态码，业务失败通过 `body.code` 表达。请按 `body.code` 断言。

**Q：UI 用例提示找不到元素或超时？**

确认前端已在 5173 运行、`web_base_url` 正确；CI 环境需加 `--headless` 并安装 Chrome。失败截图已自动挂到 Allure，可按图定位。

**Q：`pytest -n auto` 跑 UI 用例异常？**

UI 用例依赖真实浏览器与登录态，建议**串行**执行；`-n auto` 主要用于接口用例。

---

## 参与贡献

1. Fork 本仓库并新建特性分支：`git checkout -b feature/your-case`

2. 新增用例请遵循现有分层：定位器进 `pages/`、请求封装进 `api/`、断言留在 `testcases/`

3. 涉及数据变更的用例必须做**双重断言**，被拦截的场景必须验**零副作用**

4. UI 用例禁止 `time.sleep()`，统一使用 `utils/waits.py`

5. 提交前本地执行 `pytest testcases -v` 确保全绿

---

## License

本项目基于 **MIT License** 开源。

```text
MIT License

Copyright (c) 2026 LiteTrack

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
```
