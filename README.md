# LiteTrack 自动化测试框架 · 项目说明文档

> 轻舟 LiteTrack —— 轻量级敏捷项目协作与缺陷跟踪系统的接口 / Web UI 自动化测试工程。
> 本文档基于仓库当前源码梳理，覆盖工程结构、技术栈、分层职责、用例清单、核心设计与运行方式。

- **被测系统**：前后端分离，前端 Vue 3 + Element Plus，后端 Spring Boot
- **测试通道**：HTTP 接口自动化 + Selenium Web UI 自动化，两条线独立组织
- **用例框架**：pytest 8 / pytest-xdist
- **报告**：Allure
- **持续集成**：Jenkins 声明式 Pipeline
- **Python**：3.10+

---

## 一、项目概览

本仓库独立于业务代码仓库，通过 HTTP 与浏览器两条通道对被测系统做黑盒验证。

后端统一响应体为 `Result<T>`，结构为 `{ code, message, data }`。**全局异常处理器不改写 HTTP 状态码**：无权限、非法状态流转等业务失败，常见结果是 **HTTP 200，但 `body.code` 为 403 或其它业务码**。框架所有断言都对齐这条契约，按 `body.code` 判定，而不是只看 HTTP 状态码。

### 技术栈

| 分类 | 选型 |
| --- | --- |
| 用例框架 | pytest 8、pytest-xdist（接口用例并行） |
| 接口测试 | requests（`Session` 子类做角色会话隔离） |
| UI 测试 | Selenium 4，页面对象模式（POM）+ 显式等待 |
| 浏览器 | Edge（`--headless` 无头模式供 CI 使用） |
| 数据断言 | PyMySQL（DictCursor，直连 MySQL 双重断言） |
| 报告 | allure-pytest |
| 配置与数据 | PyYAML |
| 流水线 | Jenkins 声明式 Pipeline |
| 数据库 | MySQL 8.x |

### 第三方依赖（requirements.txt）

```text
pytest>=8.0
requests>=2.31
selenium>=4.11
allure-pytest>=2.13
PyYAML>=6.0
pytest-xdist>=3.5
PyMySQL>=1.1
```

---

## 二、目录结构

```text
litetracktest/
├── api/                          # 接口封装层，一个资源一个类
│   ├── auth_api.py               # 认证：登录 / 登出 / 当前用户 / 修改资料
│   ├── task_api.py               # 任务：查询 / 创建 / 修改 / 指派 / 接受 / 拒绝 / 提交 / 审核 / 删除
│   ├── bug_api.py                # 缺陷：查询 / 创建 / 指派 / 修复 / 关闭 / 重开 / 日志
│   ├── project_api.py            # 项目：CRUD / 关闭 / 重启 / 成员管理
│   ├── user_api.py               # 用户：CRUD / 状态 / 回收站 / 恢复 / 彻底删除
│   ├── notification_api.py       # 站内通知：未读统计 / 列表 / 已读 / 清空
│   ├── stats_api.py              # 统计：概览 / 缺陷状态 / 成员任务 / 缺陷趋势
│   ├── task_block_api.py          # 任务阻塞：阻塞 / 延期重启 / 重启 / 详情
│   ├── workbench_api.py          # 工作台：PM 项目汇总
│   ├── ai_chat_api.py            # AI 对话：会话管理 / SSE 流式对话 / 临时文件上传 / 缺陷优化
│   ├── ai_knowledge_api.py       # AI 知识库：上传 / 改内容 / 删除 / 列表 / 全文
│   └── upload_api.py             # 通用附件上传 / 按 URL 删除
├── pages/                        # 页面对象层（POM）
│   ├── base_page.py              # 页面基类：打开页面 / 显式等待 / 输入 / 点击
│   ├── login_page.py             # 登录页（含 LoginFailed 异常）
│   ├── task_board_page.py         # 任务看板
│   ├── bug_list_page.py          # 缺陷列表
│   ├── bug_detail_page.py        # 缺陷详情
│   ├── dashboard_page.py         # 工作台首页
│   ├── error_page.py             # 403 / 404 错误页
│   ├── knowledge_base_page.py    # 知识库
│   ├── project_manage_page.py    # 项目管理
│   ├── stats_page.py             # 统计报表
│   ├── user_manage_page.py       # 用户管理
│   ├── layout_page.py            # 整体布局
│   ├── ai_assistant_page.py      # AI 助手页面
│   └── components/               # 可复用组件
│       ├── sidebar_page.py       # 侧边导航
│       ├── navbar_page.py        # 顶栏
│       ├── notice_center.py      # 通知中心
│       ├── page_table.py         # 通用表格组件
│       └── ai_assistant.py       # AI 助手组件
├── testcases/                    # 用例层，只写业务步骤与断言
│   ├── api/                      # 接口自动化（秒级，可并行）
│   └── ui/                       # Web UI 自动化（真实浏览器，建议串行）
├── utils/                        # 工具层
│   ├── config_loader.py          # 读取 env.yaml 与 data/*.yaml
│   ├── db.py                     # PyMySQL 封装，双重断言用
│   ├── waits.py                  # WebDriverWait 显式等待封装
│   └── table_utils.py            # Element Plus 表格按表头定位列取值
├── config/
│   └── env.yaml                  # 环境地址、测试账号、数据库连接（dev / test）
├── data/
│   ├── permission_matrix.yaml    # 角色 × 接口权限矩阵
│   ├── task_audit.yaml           # 任务提交 / 审核请求体
│   └── uplodedata/               # 上传测试附件（png/gif/docx/pdf/txt）
├── sql/
│   └── seed_test_accounts.sql    # 测试账号、项目与成员造数（幂等）
├── screenshots/                  # 失败自动截图产物
├── allure-results/               # Allure 原始结果
├── conftest.py                   # 全局夹具、角色会话、造数清理、失败截图钩子
├── health_check.py               # 前后端存活自检
├── pytest.ini                    # 用例发现规则与默认参数
├── Jenkinsfile                   # Jenkins 声明式流水线
└── requirements.txt
```

---

## 三、分层职责

```text
                 ┌──────────────────────────────────────┐
                 │            testcases/                 │
                 │   api/  ──▶ 接口自动化（秒级）        │
                 │   ui/   ──▶ Web UI 自动化（浏览器）  │
                 └───────────────┬──────────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                        ▼
 ┌─────────────┐         ┌─────────────┐          ┌─────────────┐
 │  api/       │         │  pages/     │          │  utils/     │
 │  接口封装    │         │  POM 页面对象│          │ 等待/配置/DB│
 └─────────────┘         └─────────────┘          └─────────────┘
        └────────────────────────┼────────────────────────┘
                                 ▼
                    ┌──────────────────────────┐
                    │        conftest.py       │
                    │  Session / Token / 造数    │
                    │  Edge 驱动 / 失败截图夹具  │
                    └──────────────────────────┘
```

| 层次 | 目录 | 职责 |
| --- | --- | --- |
| 用例层 | `testcases/` | 只写业务断言与步骤，不含定位器与 HTTP 细节 |
| 接口层 | `api/` | 一个资源一个类，封装请求路径、参数与响应解析 |
| 页面层 | `pages/` | 页面对象，封装定位器与页面操作，与用例解耦 |
| 工具层 | `utils/` | 显式等待、配置读取、数据库直连、表格读取 |
| 夹具层 | `conftest.py` | 会话、Token、造数、浏览器、失败截图与清理 |

---

## 四、接口封装清单（api/）

| 类 | 对应控制器前缀 | 主要方法 |
| --- | --- | --- |
| `AuthApi` | `/api/auth` | `login`、`logout`、`me`、`update_profile` |
| `TaskApi` | `/api/tasks` | 分页列表、详情、审核记录、`create`、`update`、`assign`、`delete`、`accept`、`reject`、`submit`、`audit`、`find_id_by_title` |
| `BugApi` | `/api/bugs` | 分页列表、详情、`create`、`assign`、`fix`、`close`、`reopen`、`get_logs` |
| `ProjectApi` | `/api/projects` | 列表、详情、成员、`create`、`update`、`delete`、`close`、`reopen`、`add_members`、`remove_member` |
| `UserApi` | `/api/users` | 分页列表、下拉选项、回收站、`create`、`update`、`update_status`、`delete`、`restore`、`permanent_delete` |
| `NotificationApi` | `/api/notifications` | 未读统计、最近列表、单条已读、全部已读、单删、清空、分页查询 |
| `StatsApi` | `/api/stats` | 概览、缺陷状态分布、成员任务统计、缺陷趋势 |
| `TaskBlockApi` | `/api/task-blocks` | `block`、`delay`、`restart`、阻塞详情 |
| `WorkbenchApi` | `/api/workbench` | PM 负责的进行中项目汇总 |
| `AiChatApi` | `/api/ai` | 会话列表 / 创建 / 更新 / 删除、消息列表、SSE 对话、等待消息、临时文件上传、缺陷优化 |
| `AiKnowledgeApi` | `/api/ai/knowledge` | 文件上传、改内容、删除、分页列表、文件名列表、查看全文、存在即删 |
| `UploadApi` | `/api/upload` | 通用附件上传、按 URL 删除 |

### 任务状态机（后端契约）

```text
TODO ──accept──▶ DOING ──submit──▶ PENDING_REVIEW
  ▲                │                   │
  │                └──audit REJECT ───┘
  │                                    │
  └────────────── audit PASS ──────────▶ DONE
```

---

## 五、用例清单

> 统计口径：含 `@pytest.mark.parametrize` 展开后的参数化实例。当前共 **约 74 条**，其中接口 **约 39 条**、UI **约 35 条**。

### 5.1 接口用例（testcases/api/）

| 文件 | 用例 / 参数化 | 验证点 |
| --- | --- | --- |
| `test_auth_api.py` | `test_login_success` | 正确账号密码登录，返回 token 与用户信息 |
| | `test_login_fail` | 错误密码登录，抛出「用户名或密码错误」 |
| | `test_update_profile` | 修改个人姓名后回读校验，`finally` 复原原名 |
| `test_ai_module.py` | `test_create_session_default_title` | 空标题回落「新对话」，会话进入列表 |
| | `test_create_with_title_and_rename` | 带标题创建后可重命名 |
| | `test_pin_sorts_first` | 置顶会话排到第一位 |
| | `test_delete_session_cascade` | 删除会话级联清理其消息 |
| | `test_sse_contract_and_persistence` | SSE 流式返回契约与消息落库（slow） |
| | `test_session_isolation` | 不同会话消息互相隔离（slow） |
| | `test_empty_message_rejected` | 空消息被拦截（slow） |
| | `test_unknown_session_rejected` | 未知会话 ID 被拦截（slow） |
| | `test_upload_temp_extracts_text` | 临时文件上传并提取文本 |
| | `test_optimize_bug` | AI 缺陷描述优化 |
| `test_bug_lifecycle.py` | `test_bug_full_flow` | QA 提交 → DEV 修复 → QA 关闭，DB 状态 OPEN→FIXED→CLOSED 双重断言 |
| `test_permission_matrix.py` | `test_sensitive_endpoints`（12 条） | 4 角色 × accept/audit/assign 三接口，按 YAML 期望业务码断言 |
| `test_project_api.py` | `test_project_crud` | 创建 → 列表查到 → 关闭 → 重启 → 删除，状态回读校验 |
| `test_task_permission.py` | `test_audit_permission_matrix`（2 条） | DEV 调审核 `code=403`；PM 在待审核状态审核 `code=200` |
| `test_task_state_machine.py` | `test_task_happy_path_with_db` | 建单 → 接受 → 提交 → 打回 → 重提 → 通过，DB 逐步核对状态 |
| `test_task_validation.py` | `test_create_task_invalid_params`（3 条） | 标题为空 / 项目 ID 为空 / 负责人不存在，均被拦截且报错信息匹配 |
| `test_upload_api.py` | `test_upload_all_valid_file`（5 条） | png / gif / docx / pdf / txt 上传成功返回 http URL，finally 清理 |
| `test_workbench_notification.py` | `test_notification_flow` | 未读统计 → 消息列表 → 单条已读 → 全部已读 → 清空 |

### 5.2 UI 用例（testcases/ui/）

| 文件 | 用例 | 验证点 |
| --- | --- | --- |
| `test_login_flow.py` | `test_admin_login_success` | admin 登录后跳转 `/dashboard`，顶栏展示登录人 |
| | `test_admin_login_by_enter` | 回车提交可完成登录 |
| | `test_login_wrong_password` | 密码错误提示 |
| | `test_login_user_not_exist` | 用户不存在提示 |
| | `test_login_empty_username` | 用户名为空拦截 |
| | `test_login_empty_password` | 密码为空拦截 |
| | `test_login_logout_clear_token` | 登出后 token 被清除 |
| `test_ui_ai_assistant.py` | `test_panel_toggle` | 助手面板展开 / 收起 |
| | `test_maximize_and_restore` | 最大化与还原 |
| | `test_empty_input_keeps_send_disabled` | 空输入时发送按钮禁用 |
| | `test_enter_sends_and_shift_enter_newline` | Enter 发送、Shift+Enter 换行 |
| | `test_send_message_and_markdown` | 发送消息并渲染 Markdown |
| | `test_stop_generating` | 停止生成 |
| | `test_new_chat_resets_and_adds_history` | 新对话重置并加入历史 |
| | `test_history_switch_active` | 历史会话切换高亮 |
| | `test_pin_moves_to_first` | 置顶会话移到首位 |
| | `test_rename_and_delete` | 会话重命名与删除 |
| | `test_attachment_upload_and_preview` | 附件上传与预览 |
| `test_ui_bug_lifecycle.py` | `test_bug_full_lifecycle_dashboard` | 缺陷全流程与看板联动 |
| `test_ui_error_pages.py` | `test_404_page_not_found` | 404 页面展示 |
| | `test_403_forbidden_access` | 403 页面展示 |
| `test_ui_global_components.py` | `test_notice_center_operations` | 通知中心查看 / 已读等操作 |
| `test_ui_manage_operations.py` | `test_create_user_flow` | 管理员新建用户流程 |
| | `test_project_member_readonly_check` | 项目成员只读，不可编辑 |
| `test_ui_permission_isolation.py` | `test_dev_cannot_see_admin_menus` | DEV 不可见管理员菜单 |
| | `test_dev_cannot_see_edit_buttons_on_task_board` | DEV 看板不可见编辑按钮 |
| `test_ui_stats_report.py` | `test_stats_admin_view` | 管理员视角统计报表 |
| | `test_stats_dev_view` | 开发视角统计报表 |
| `test_ui_task_flow.py` | `test_create_task_appears_on_board` | PM 新建任务后出现在看板表格 |
| | `test_accept_task_updates_status` | DEV 接受任务，状态变「进行中」，DB 落库 `DOING` |
| `test_ui_knowledge_base.py` | `test_upload_and_edit_knowledge` | 知识库文件上传与内容编辑 |
| | `test_dev_view_then_admin_cleanup` | DEV 视角查看，管理员清理 |
| | `test_level_1_all_visible` | L1 知识库全员可见 |
| | `test_level_2_ai_only` | L2 仅 AI 助手可见 |
| | `test_level_3_admin_only` | L3 仅管理员可见 |

---

## 六、核心设计

### 6.1 统一响应契约与断言方式

后端 `Result` 结构为 `{ code, message, data }`，全局异常处理器不改写 HTTP 状态码：

- **成功**：HTTP 200 且 `body.code == 200`
- **业务失败 / 无权限**：HTTP 200 且 `body.code == 403` 或其它业务码

用例统一按 `body.code` 断言，而非 HTTP 状态码。

### 6.2 双重断言：接口 + 数据库

先用接口拿到业务响应，再用 `utils/db.py` 直连同一条记录核对，两边互为印证：

```python
def test_xxx(task_api, pm_token, db, todo_task_id):
    resp = task_api.accept(pm_token, todo_task_id)
    assert resp.json()["code"] == 200
    assert db.fetch_task(todo_task_id)["status"] == "DOING"
```

`DBClient` 基于 PyMySQL + DictCursor，提供 `query` / `query_one` / `execute` / `fetch_task` / `fetch_bug`，连接随用随关、写操作显式提交。

### 6.3 零副作用断言

越权或非法流转被拦截时，比对拦截前后的字段快照，确保数据库零变更：

```python
before = _snapshot(db, task_id)
resp = dev_client.patch(f"/api/tasks/{task_id}/audit", json={"auditResult": "PASS"})
assert resp.json()["code"] == 403
assert _snapshot(db, task_id) == before      # 一个字段都不能动
```

### 6.4 权限矩阵数据驱动

角色与接口的对应关系外置到 `data/permission_matrix.yaml`，用例通过 `get_matrix_cases()` 读取后用 `@pytest.mark.parametrize` 展开为笛卡尔积。新增角色或调整规则时只改 YAML，不动用例代码。

```yaml
endpoints:
  audit:
    method: PATCH
    path: /api/tasks/{task_id}/audit
    pre_state: PENDING_REVIEW
matrix:
  - role: DEV
    account: dev01
    client_fixture: dev_client
    expected: { accept: 200, audit: 403, assign: 403 }
```

### 6.5 角色会话隔离（RoleClient）

`RoleClient` 继承 `requests.Session`，一个角色一个实例，Token 进入实例私有头，避免多角色并行时串号。请求路径只写 `/api/xxx`，自动补 base_url。

> 注意：会话级**不设置** `Accept` / `Content-Type`。会话级 Content-Type 会覆盖 requests 按 `files=` 自动生成的 multipart 头，导致后端抛 `not a multipart request`；会话级 `Accept: application/json` 会让 SSE 接口（`produces=text/event-stream`）在媒体类型匹配阶段就被拒绝。不写这两个头时，requests 按场景自动补 `application/json` 或 `multipart/form-data`，Accept 缺省 `*/*`，JSON 与 SSE 都能接受。

### 6.6 页面对象与显式等待

定位器基于真实前端源码，页面元素与用例逻辑解耦。`utils/waits.py` 统一封装 `WebDriverWait` + `expected_conditions`，**禁止 `time.sleep()`**：

| 封装 | 作用 |
| --- | --- |
| `wait_for_element_visible` | 等待元素出现且可见 |
| `wait_for_element_clickable` | 等待元素可见且可点击 |
| `wait_for_url_contains` | 等待地址栏包含指定片段 |
| `wait_for_first_displayed` | 等待匹配项中第一个「可见」元素（适配 Element Plus 常驻 DOM、`display:none` 的下拉面板） |
| `wait_for_element_invisible` | 等待元素不可见 |
| `wait_for_element_not_disabled` | 等待元素移除 `disabled` 属性（适配表单校验通过后才可提交） |

`utils/table_utils.py` 按表头文字定位列序号，再依据 `td` 上的 `el-table_N_column_M` class 精确取单元格，避免列顺序变化时静默读错值。

### 6.7 失败自动截图

`pytest_runtest_makereport` 钩子在用例失败且浏览器仍存活时抓图，写入 `screenshots/`，并作为 PNG 挂载到 Allure 对应用例，无需在用例里写截图代码。

### 6.8 造数与清理策略

- **项目单例**：整个 session 最多创建 1 个项目。优先级：`env.yaml.project_id` → 复用可见项目 → PM 新建带 DEV/QA 成员的项目；teardown 只删本次自建的项目。
- **任务夹具**：
  - `todo_task_id`：PM 创建指派给 DEV 的 TODO 任务，`yield` 出 ID，结束删除。
  - `setup_task`：PM 创建并推进到待审核（accept → submit），结束删除。
  - `task_cleaner`：登记式清理，UI 用例把标题交登记，teardown 按标题查 ID 再删；中途失败也会清理。
- 清理失败只告警，不掩盖用例本身的失败。

---

## 七、配置说明

### 7.1 config/env.yaml

| 键 | 说明 |
| --- | --- |
| `active` | 默认环境名，当前为 `dev` |
| `api_base_url` | 后端根地址，不要带 `/api`（代码会拼） |
| `web_base_url` | 前端根地址 |
| `project_id` | 造数项目 ID，留空时夹具用 PM 账号取可见项目第一条或新建 |
| `task_id` | 复用现成任务时填写，与 `project_id` 二选一 |
| `accounts` | `admin` / `pm01` / `dev01` / `qa01` 的用户名与密码（密码加引号，避免被 YAML 读成数字） |
| `db` | 数据库直连参数，供双重断言使用 |

切换环境不改文件：

```powershell
# Windows PowerShell
$env:LITETRACK_ENV = "test"
pytest testcases/api
```

### 7.2 测试账号（sql/seed_test_accounts.sql）

| 账号 | 角色 | 明文口令 |
| --- | --- | --- |
| `admin` | ADMIN | 123456 |
| `pm01` | PM | 123456 |
| `dev01` | DEV | 123456 |
| `qa01` | QA | 123456 |

脚本幂等，可重复执行：账号走 `ON DUPLICATE KEY UPDATE`，项目与成员用 `NOT EXISTS` 兜底。口令为 BCrypt（`$2a$`，strength=10）密文，与后端 spring-security-crypto 一致。

### 7.3 已封装夹具（conftest.py）

| 夹具 | 作用 |
| --- | --- |
| `env` | 当前环境字典 |
| `api_session` | 复用的 `requests.Session()` |
| `login` | `login("dev01")` 返回 `{token, user}`，同一账号只登录一次 |
| `admin_token` / `pm_token` / `dev_token` / `qa_token` | 各角色 JWT |
| `admin_client` / `pm_client` / `dev_client` / `qa_client` | 绑定角色 Token 的 `RoleClient`，默认头已带 `Authorization` |
| `no_auth_client` | 无 Token 匿名会话，用于未登录鉴权测试 |
| `db` | `DBClient`，数据库直连双重断言 |
| `todo_task_id` / `setup_task` / `task_cleaner` | 任务造数与登记式清理 |
| `driver` | Edge 浏览器；`--headless` 无头，用例结束 `quit` |
| `logged_in_driver` | 真实账号密码登录后落在 `/dashboard` |
| `switch_role` | 登出当前账号再用目标账号完整登录，返回切换后 URL |
| `login_page` / `task_board_page` / `sidebar` / `notice_center` | 页面对象与组件 |

Token 请求头格式与后端 `JwtInterceptor` 一致：`Authorization: Bearer <token>`。

### 7.4 pytest.ini

```ini
[pytest]
testpaths = testcases
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --strict-markers --alluredir=./allure-results --clean-alluredir
pythonpath = .
markers =
    api: 接口自动化用例
    ui: Web UI 自动化用例
    slow: mark test as slow running test
```

---

## 八、快速开始

按顺序：**后端 → 前端 → 造数 → 自检 → 跑用例**。

### 0. 前置条件

- Python 3.10+、MySQL 8.x、Edge 浏览器
- 后端仓库（Spring Boot :8080）与前端仓库（Vite :5173）已就绪
- 安装依赖：

```bash
python -m pip install -r requirements.txt
```

### 1. 启动后端（Spring Boot）

```bash
mvn clean package -DskipTests
java -jar target/*.jar
```

看到 `Started LiteTrackApplication` 即就绪。

### 2. 启动前端（Vite）

```bash
npm install
npm run dev
```

`/api` 已代理到后端 8080，框架直接访问 5173 即可。

### 3. 造数（初始化账号与项目）

```bash
mysql -uroot -p123456 litetrack < sql/seed_test_accounts.sql
```

或在 Navicat 中整段执行脚本。

### 4. 环境自检

```bash
python health_check.py
```

预期输出：

```text
[OK  ] 后端 api  http://192.168.100.128  ->  HTTP 200
[OK  ] 前端 web  http://192.168.100.128  ->  HTTP 200
环境自检通过（env=dev）
```

任一服务不可用打印 `[FAIL]` 并以非 0 退出码结束，可作为流水线前置关卡。

### 5. 执行用例

```bash
# 全部用例
pytest testcases -v

# 只跑接口（快，可并行）
pytest testcases/api -v
pytest testcases/api -n auto

# 只跑 UI（有界面）；无界面环境加 --headless
pytest testcases/ui -v
pytest testcases/ui -v --headless
```

> UI 用例依赖真实浏览器与登录态，建议串行执行；`-n auto` 主要用于接口用例。

### 6. 查看 Allure 报告

```bash
pytest testcases -v
allure serve ./allure-results
```

---

## 九、持续集成（Jenkinsfile）

声明式流水线，接口与 UI 分两次执行、分目录写入结果，避免第二次 `--clean-alluredir` 清掉第一次的结果：

| 阶段 | 动作 |
| --- | --- |
| Checkout | `checkout scm` |
| Install | 升级 pip，安装 `requirements.txt`（Unix 用 `sh`，Windows 用 `bat`） |
| Run API Tests | `pytest testcases/api --alluredir=allure-results/api --clean-alluredir`，失败记 `UNSTABLE` |
| Run UI Tests | `pytest testcases/ui --headless --alluredir=allure-results/ui --clean-alluredir` |
| Generate Allure Report | `allure generate` 合并两份结果到 `allure-report` 并归档 |

节点要求：能访问被测环境、已安装 Edge/Chrome 与 Allure Commandline。

---

## 十、常见问题

**Q：登录返回 401 / 「用户名或密码错误」？**
数据库缺少 `pm01` / `dev01` / `qa01` 账号，执行 `sql/seed_test_accounts.sql` 补齐即可，口令统一 `123456`。

**Q：夹具报「PM 账号下没有可用项目」？**
脚本会创建造数项目并把 `pm01` 设为 owner；若用自有项目，把项目 ID 填到 `env.yaml` 的 `project_id`。

**Q：接口断言 `code != 200`，但 HTTP 是 200？**
这是后端正常契约：业务失败通过 `body.code` 表达，按 `body.code` 断言即可。

**Q：UI 用例找不到元素或超时？**
确认前端已启动、`web_base_url` 正确；CI 环境加 `--headless` 并安装浏览器。失败截图已挂到 Allure，可按图定位。

**Q：上传用例报 `not a multipart request`？**
检查会话级是否误设了 `Content-Type: application/json`；`RoleClient` / `api_session` 刻意不设该头，由 requests 按 `files=` 自动生成 multipart 头。

---

## 十一、扩展规范

1. 新增用例遵循现有分层：定位器进 `pages/`、请求封装进 `api/`、断言留在 `testcases/`。
2. 涉及数据变更的用例必须做**双重断言**；被拦截场景必须验**零副作用**。
3. UI 用例禁止 `time.sleep()`，统一使用 `utils/waits.py`。
4. 权限规则调整只改 `data/permission_matrix.yaml`。
5. 提交前本地执行 `pytest testcases -v` 确保全绿。
