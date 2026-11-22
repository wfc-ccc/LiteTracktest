import os
from pathlib import Path

import allure
import pytest


# 账号兜底值：正常走 env.yaml 的 accounts，这里只在 env 缺字段时用
FALLBACK_ACCOUNTS = {
    "admin": ("admin", "123456"),
    "dev01": ("dev01", "123456"),
}

# 能直接断言正文的纯文本类型
TEXT_SUFFIX = {".txt", ".md"}
# 能上传但正文只能弱断言的类型（白名单里没有 png/gif）
DOC_SUFFIX = {".pdf", ".doc", ".docx"}
USABLE_SUFFIX = TEXT_SUFFIX | DOC_SUFFIX

# True：跑完保留这份数据（DEV 权限用例需要有行数据才能验证行内按钮）
KEEP_DATA = True

# 模块级标记：本进程内 ADMIN 用例是否真的把数据落进库里了
KB_SEEDED = False


# ======================================================================
# 工程根 / 素材目录定位
# 目录名不要再写死：工程里实际叫 data/uplodedata（少一个 a），
# 不是 data/uploadedata。这里改成扫 data/ 下的子目录自动识别。
# ======================================================================
def _project_root(request=None) -> Path:
    candidates = []

    try:
        candidates.append(Path(request.config.rootpath))
    except Exception:
        pass

    here = Path(__file__).resolve()
    candidates.extend(here.parents)
    candidates.append(Path.cwd())

    seen, ordered = set(), []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            ordered.append(c)

    for c in ordered:
        if (c / "config" / "env.yaml").is_file() and (c / "data").is_dir():
            return c
    for c in ordered:
        if (c / "data").is_dir():
            return c
    return here.parents[2]


def _usable_files(d: Path) -> list:
    """列出目录下能上传的非空文件（按后缀白名单过滤）。"""
    try:
        names = list(os.listdir(d))
    except Exception:
        return []
    out = []
    for n in names:
        p = d / n
        try:
            if p.is_file() and p.suffix.lower() in USABLE_SUFFIX and p.stat().st_size > 0:
                out.append(n)
        except Exception:
            continue
    return out


def _base_data_dir(root: Path) -> Path:
    """优先复用项目自己的 utils.config_loader.DATA_DIR，取不到再回退 root/data。"""
    try:
        from utils.config_loader import DATA_DIR as proj_data_dir
        p = Path(proj_data_dir)
        if p.is_dir():
            print(f"[KB] 采用 utils.config_loader.DATA_DIR = {p}")
            return p
    except Exception as e:
        print(f"[KB] 未能复用 utils.config_loader.DATA_DIR"
              f"（{type(e).__name__}: {e}），改用 {root / 'data'}")
    return root / "data"


def _data_dir(request=None) -> Path:
    """返回放上传素材的目录：扫 data/ 下所有子目录，挑有素材的那个。

    目录名不写死，是因为 IDE 树里显示的和磁盘上可能有出入；
    名字里带 'load'（uploadedata / uplodedata 都带）的优先，
    其次是文件多的。一个都没有就把 data/ 的完整明细打出来。
    """
    root = _project_root(request)
    base = _base_data_dir(root)
    print(f"[KB] 工程根 = {root}")

    if not base.is_dir():
        pytest.fail(f"工程根下没有 data 目录：{base}")

    entries = sorted(os.listdir(base))
    print(f"[KB] data 下所有项 = {[repr(n) for n in entries]}")

    cands = []
    for n in entries:
        p = base / n
        if p.is_dir():
            files = _usable_files(p)
            if files:
                cands.append((0 if "load" in n.lower() else 1, -len(files), n, p))

    if not cands:
        if _usable_files(base):
            print(f"[KB] data 根目录下直接有可用文件，使用 {base}")
            return base
        detail = []
        for n in entries:
            p = base / n
            detail.append(f"{n!r}(is_dir={p.is_dir()}, usable={_usable_files(p) if p.is_dir() else '-'})")
        pytest.fail(
            f"{base} 下没有找到可上传的素材（支持 {'/'.join(sorted(USABLE_SUFFIX))}）。"
            f"明细：{detail}"
        )

    cands.sort()
    for key, _neg, name, path in cands:
        print(f"[KB] 候选目录 {name!r} → {_usable_files(path)}")
    chosen = cands[0][3]
    print(f"[KB] 选用数据目录 = {chosen}")
    return chosen


def _pick_data_file(d: Path) -> tuple:
    """从素材目录里挑一个文件，返回 (路径, 'text'|'doc')。

    优先含「知识库」的 txt/md，其次任意 txt/md，再退到 docx/pdf。
    """
    try:
        entries = list(os.listdir(d))
    except Exception as e:
        pytest.fail(f"读取目录失败：{d} → {type(e).__name__}: {e}")

    picks = []
    for n in entries:
        p = d / n
        if not p.is_file():
            continue
        suffix = p.suffix.lower()
        if suffix in TEXT_SUFFIX:
            picks.append((0, 0 if "知识库" in n else 1, n, p, "text"))
        elif suffix in DOC_SUFFIX:
            picks.append((1, 0 if "知识库" in n else 1, n, p, "doc"))

    if not picks:
        pytest.fail(
            f"{d} 下没有可上传的文件。实际内容（repr 显示真实字符）："
            f"{[repr(n) for n in entries]}"
        )

    picks.sort(key=lambda x: x[:3])
    _mode_rank, _name_rank, _n, chosen, mode = picks[0]
    size = chosen.stat().st_size
    print(f"[KB] 选用测试数据：{chosen}")
    print(f"[KB] 文件名 repr={chosen.name!r}，大小={size} 字节，模式={mode}")
    print(f"[KB] 目录内所有项={[repr(n) for n in entries]}")
    if size == 0:
        pytest.fail(f"数据文件是空的：{chosen}")
    return chosen, mode


def _account(env: dict, key: str) -> tuple:
    """从 env.yaml 的 accounts 取账号，缺失才用兜底值。"""
    acc = (env.get("accounts") or {}).get(key) or {}
    user = acc.get("username") or FALLBACK_ACCOUNTS[key][0]
    pwd = acc.get("password") or FALLBACK_ACCOUNTS[key][1]
    return str(user), str(pwd)


@allure.feature("UI 自动化")
@allure.story("知识库管理")
class TestKnowledgeBaseUI:

    @pytest.fixture
    def kb_page(self, driver, env):
        from pages.knowledge_base_page import KnowledgeBasePage
        return KnowledgeBasePage(driver, env["web_base_url"])

    @pytest.fixture
    def login_page(self, driver, env):
        from pages.login_page import LoginPage
        return LoginPage(driver, env["web_base_url"])

    # ------------------------------------------------------------------
    def _switch_account(self, driver, env, login_page, login,
                        account: str, password: str = None) -> None:
        """切账号：走真实 UI 登录（userStore.role 才会正确装起来）。

        注意 token 注入必须先导航到站点源：新会话初始页是 data:,
        在非 http 源上访问 localStorage 会抛 SecurityError。
        """
        base = env["web_base_url"].rstrip("/")

        if password:
            if not driver.current_url.startswith(base):
                driver.get(base + "/login")
            try:
                login_page.logout()
            except Exception as e:
                print(f"[KB-AUTH] logout 跳过（{type(e).__name__}），继续登录")
            login_page.wait_login_page_display()
            login_page.login(username=account, password=password)
            login_page.wait_until_logged_in()
            print(f"[KB-AUTH] ✅ UI 登录成功：{account}，URL={driver.current_url}")
            return

        token = login(account)["token"]
        if not driver.current_url.startswith(base):
            print(f"[KB-AUTH] 当前页 {driver.current_url} 不是站点源，先导航到 /login")
            driver.get(base + "/login")
        driver.execute_script(
            "window.localStorage.setItem('litetrack_token', arguments[0]);", token
        )
        assert driver.execute_script(
            "return window.localStorage.getItem('litetrack_token');"
        ), "token 没有写进 localStorage"
        print(f"[KB-AUTH] ⚠️ 仅注入 token（{token[:8]}...），role 可能未加载")

    # ------------------------------------------------------------------
    @allure.title("ADMIN 上传知识文件、查看详情并修改内容")
    def test_upload_and_edit_knowledge(self, kb_page, driver, env,
                                       login_page, login, request):
        global KB_SEEDED

        data_file, mode = _pick_data_file(_data_dir(request))
        file_name = data_file.name
        if mode == "text":
            original = data_file.read_text(encoding="utf-8", errors="ignore")
        else:
            original = ""              # docx/pdf 读不出纯文本，正文只做弱断言
        probe = "".join(original.split())[:20]
        appended = "\n【UI 自动化追加】内容已更新"
        admin_user, admin_pwd = _account(env, "admin")
        print(f"[KB] 使用账号 {admin_user}（来自 env.accounts）")

        with allure.step("1. 切换 ADMIN 账号并打开知识库"):
            self._switch_account(driver, env, login_page, login,
                                 admin_user, admin_pwd)
            kb_page.open()
            kb_page.debug_identity("ADMIN 打开知识库后")
            assert kb_page.is_element_visible(kb_page.BTN_UPLOAD) is True, (
                "ADMIN 看不到「上传知识」按钮。源码判定是 "
                "isAdmin = userStore.role === 'ADMIN'（严格全等）。"
                f"当前探测到的 role = {kb_page.current_role()!r}；"
                "若为 None，说明 userStore 身份没加载；"
                "若为 'ROLE_ADMIN'/'admin' 等其它写法，是角色字符串不匹配，属于前端问题。"
            )

        try:
            with allure.step("1.5 前置清理：历史临时文件 + 同名旧文件"):
                try:
                    kb_page.cleanup_by_prefix("UI测试文档_")   # 之前随机名用例的残留
                    kb_page.delete_if_exists(file_name)        # 同名会被后端判重，先删
                except Exception as e:
                    print(f"[KB-CLEANUP] ⚠️ 预清理失败（不影响主流程）：{type(e).__name__}: {e}")

            with allure.step(f"2. 上传数据文件：{file_name}"):
                kb_page.open_upload_dialog()
                kb_page.upload_file(str(data_file), access_level="全员访问")
                kb_page.wait_message("上传成功")
                kb_page.search(file_name)
                assert kb_page.wait_row(file_name) is True, \
                    f"上传后列表里没有 {file_name}"

            with allure.step("3. 查看文件详情"):
                text = kb_page.view_file(file_name)
                assert kb_page.drawer_title().startswith("查看文件："), \
                    f"抽屉标题不对：{kb_page.drawer_title()!r}"
                if probe:
                    assert probe in "".join(text.split()), \
                        f"抽屉内容与源文件不一致：期望含 {probe!r}，实际 {text[:120]!r}"
                else:
                    assert text.strip(), f"{mode} 文件解析后正文为空：{text[:120]!r}"
                    print(f"[KB] {mode} 文件正文前 120 字：{text[:120]!r}")
                kb_page.close_drawer()

            with allure.step("4. 编辑并保存内容"):
                kb_page.click_row_action(file_name, "查看")
                kb_page.wait_drawer_content()
                kb_page.click_drawer_btn("编辑")
                kb_page.set_edit_content(original + appended)
                kb_page.click_drawer_btn("保存")
                kb_page.wait_message("保存成功")
                assert "UI 自动化追加" in kb_page.get_drawer_content(), \
                    "保存后抽屉内容没刷新"
                kb_page.close_drawer()

            with allure.step("5. 反向校验：重新打开确认内容已落库"):
                # 保存不改变列表筛选条件，先直接找；找不到再搜
                if not kb_page.row_exists(file_name, timeout=5):
                    kb_page.search(file_name)
                assert kb_page.wait_row(file_name) is True, \
                    f"保存后列表里找不到 {file_name}，当前列表：{kb_page.row_files()}"
                text = kb_page.view_file(file_name)
                assert "UI 自动化追加" in text, \
                    f"重新打开后内容未持久化：{text[:120]!r}"
                kb_page.close_drawer()

            with allure.step("6. 断言访问权限列与行操作（ADMIN）"):
                assert kb_page.is_element_visible(kb_page.COL_ACCESS_LEVEL_HEADER) is True, \
                    "ADMIN 应该能看到「访问权限」列"
                actions = kb_page.row_action_texts(file_name)
                assert "删除" in actions, \
                    f"ADMIN 行内应该有删除按钮，实际：{actions}"

            KB_SEEDED = True

        finally:
            with allure.step("7. 收尾"):
                if KEEP_DATA:
                    print(f"[KB] 保留 {file_name} 作为知识库基准数据"
                          "（DEV 权限用例依赖它；下次运行会先删后重传）")
                else:
                    try:
                        kb_page.search(file_name)
                        if kb_page.row_exists(file_name, timeout=10):
                            kb_page.delete_file(file_name)
                            print(f"[KB-CLEANUP] ✅ 已删除 {file_name}")
                    except Exception as e:
                        print(f"[KB-CLEANUP] ⚠️ 清理失败（不影响主断言）："
                              f"{type(e).__name__}: {e}")

    # ------------------------------------------------------------------
    @allure.title("DEV 账号权限隔离：无权上传和删除")
    def test_dev_permissions_on_kb(self, kb_page, driver, env, login_page, login):
        dev_user, dev_pwd = _account(env, "dev01")

        with allure.step("切换 DEV 账号并打开知识库"):
            self._switch_account(driver, env, login_page, login, dev_user, dev_pwd)
            kb_page.open()
            kb_page.debug_identity("DEV 打开知识库后")

        with allure.step("先确认身份真的切过来了（否则后面的断言是假阴性）"):
            role = kb_page.current_role()
            assert role == "DEV", f"DEV 账号的角色应为 'DEV'，实际 {role!r}"

        with allure.step("验证隐藏的破坏性操作"):
            assert kb_page.is_element_visible(kb_page.BTN_UPLOAD) is False, \
                "DEV 不应看到上传按钮"
            assert kb_page.is_element_visible(kb_page.COL_ACCESS_LEVEL_HEADER) is False, \
                "DEV 不应看到「访问权限」列"

            row_files = kb_page.row_files()
            if not row_files:
                if KB_SEEDED:
                    pytest.fail(
                        "ADMIN 用例报告上传成功，但 DEV 这边看到空列表 —— "
                        "同一份数据两个角色可见性不一致，属于权限/可见范围问题"
                    )
                pytest.skip(
                    "知识库当前没有数据（ADMIN 用例未成功执行），"
                    "无法验证行内按钮；先单独跑 test_upload_and_edit_knowledge"
                )

            actions = kb_page.first_row_action_texts()
            assert "删除" not in actions, f"DEV 行内不应有删除按钮，实际：{actions}"
            print(f"[KB] DEV 第一行文件：{row_files[0]}，操作按钮：{actions}")
