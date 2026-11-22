"""知识库管理 UI 用例（单类，5 条）。

主体闭环（前两条）：
1. ADMIN 上传 → 查看详情 → 编辑保存 → 重新打开确认落库
2. 切到 DEV，确认员工能看到这份文件、且内容里带着 ADMIN 的修改
3. 切回 ADMIN，把这个文件删掉（DEV 无权删除），库里不留垃圾

访问权限矩阵（后三条，1/2/3 三档）：
ADMIN 上传 → 核「访问权限」标签 → 查库核 embedding（AI 侧能否检索）
→ 员工视角核可见性 → 回 ADMIN 删除

职责分三层：
- 登录切换 → login_page.login_as(env, "admin"/"dev01"/"qa01")
- 素材文件 → kb_data fixture 与 _kb_file_of（测试数据问题，不是页面能力）
- 页面读取/等待/诊断 → kb_page（pages/knowledge_base_page.py）

全程显式等待，不使用 time.sleep。
"""
from __future__ import annotations

from pathlib import Path

import allure
import pytest

from utils.config_loader import DATA_DIR     # 工程根 / data

TEXT_SUFFIX = {".txt", ".md"}                 # 正文可直接断言的类型
DOC_SUFFIX = {".pdf", ".doc", ".docx"}        # 能上传，正文只能弱断言

# 跨用例传递：ADMIN 本轮上传的文件名（DEV 用例据此校验内容、据此收尾删除）
SEEDED_FILE = ""
# 跨用例标记：ADMIN 主流程是否完整跑完（上传+编辑+校验都过了）
KB_SEEDED = False


def _kb_files() -> list:
    """data/ 下所有可上传素材，已按「txt/md 优先 → 名字含知识库 → 字典序」排好序。

    不写死目录名（磁盘上是 data/uplodedata，少一个 a），
    只认「含素材的目录」：名字带 load 的优先，其次文件多的。
    """
    for d in sorted(Path(DATA_DIR).iterdir(),
                    key=lambda p: ("load" not in p.name.lower(), p.name)):
        files = [p for p in d.iterdir()
                 if p.is_file() and p.suffix.lower() in TEXT_SUFFIX | DOC_SUFFIX
                 and p.stat().st_size] if d.is_dir() else []
        if files:
            files.sort(key=lambda p: (p.suffix.lower() not in TEXT_SUFFIX,
                                      "知识库" not in p.stem, p.name))
            print(f"[KB] 素材目录 = {d}，可用文件 = "
                  f"{[(p.name, p.stat().st_size) for p in files]}")
            return files
    pytest.fail(f"{DATA_DIR} 下没有可上传的 txt/md/docx/pdf 素材，"
                f"实际内容：{[p.name for p in Path(DATA_DIR).iterdir()]}")


def _kb_file() -> tuple:
    """默认素材：排第一的那个，返回 (路径, 'text'|'doc')。"""
    chosen = _kb_files()[0]
    return chosen, "text" if chosen.suffix.lower() in TEXT_SUFFIX else "doc"


def _kb_file_of(*suffixes: str) -> Path:
    """按后缀取素材（权限用例需要三个不同的文件，避免重名被判重）。"""
    for p in _kb_files():
        if p.suffix.lower() in suffixes:
            return p
    pytest.skip(f"data 目录里没有 {'/'.join(suffixes)} 类型的素材，"
                f"权限矩阵用例需要不同后缀的文件各一份")


def _chunk_stats(env, file_name: str) -> tuple:
    """查 ai_knowledge_chunk，返回 (分块数, 带向量的分块数)。

    init.sql 里 AI 侧的唯一判据就是 embedding：
    级别 1/2 正常切块 + 向量化；级别 3 免切块，embedding 全 NULL，
    余弦相似度算不出来，所以 AI 检索命中不了。列表可见性则看 access_level。
    """
    import pymysql
    cfg = env.get("db") or {}
    conn = pymysql.connect(
        host=cfg.get("host", "localhost"),
        port=int(cfg.get("port", 3306)),
        user=cfg.get("user", "root"),
        password=str(cfg.get("password", "123456")),
        database=cfg.get("database", cfg.get("name", "litetrack")),
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*), COUNT(embedding) FROM ai_knowledge_chunk "
                        "WHERE file_name = %s", (file_name,))
            return cur.fetchone()
    finally:
        conn.close()


@allure.feature("UI 自动化")
@allure.story("知识库管理")
class TestKnowledgeBaseUI:

    @pytest.fixture
    def kb_page(self, driver, env):
        from pages.knowledge_base_page import KnowledgeBasePage
        return KnowledgeBasePage(driver, env["web_base_url"])

    @pytest.fixture
    def kb_data(self) -> tuple:
        """(素材路径, 'text'|'doc')"""
        return _kb_file()

    # login_page 由 conftest 提供

    @allure.title("ADMIN 上传知识文件、查看详情并修改内容")
    def test_upload_and_edit_knowledge(self, kb_page, env, login_page, kb_data):
        global KB_SEEDED, SEEDED_FILE

        data_file, mode = kb_data
        file_name = data_file.name
        if mode == "text":
            original = data_file.read_text(encoding="utf-8", errors="ignore")
        else:
            original = ""   # docx/pdf 读不出纯文本，正文只做弱断言

        probe = "".join(original.split())[:20]
        appended = "\n【UI 自动化追加】内容已更新"

        with allure.step("1. 切换 ADMIN 账号并打开知识库"):
            login_page.login_as(env, "admin")
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
            with allure.step(f"2. 上传数据文件：{file_name}"):
                # 不做前置清理：库里已有同名文件时后端会判重，
                # 报错信息见 wait_message 打印的当前 toast，手动删一条即可再跑。
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

            SEEDED_FILE = file_name
            KB_SEEDED = True

        finally:
            with allure.step("7. 数据交接：留给 DEV 用例校验，删除在那边收尾"):
                if KB_SEEDED:
                    print(f"[KB] 保留 {file_name} 给 DEV 用例查看，"
                          "查看完由 DEV 用例切回 ADMIN 删除")
                else:
                    # 主流程中途失败，别把半截数据留在库里
                    try:
                        kb_page.search(file_name)
                        if kb_page.row_exists(file_name, timeout=10):
                            kb_page.delete_file(file_name)
                            print(f"[KB-CLEANUP] ✅ 主流程未完成，已删除残留 {file_name}")
                    except Exception as e:
                        print(f"[KB-CLEANUP] ⚠️ 清理失败（不影响主断言）："
                              f"{type(e).__name__}: {e}")

    # ------------------------------------------------------------------
    @allure.title("DEV 查看修改后的文件，再回 ADMIN 端删除")
    def test_dev_view_then_admin_cleanup(self, kb_page, env, login_page):
        global KB_SEEDED

        with allure.step("1. 切换 DEV 账号并打开知识库"):
            login_page.login_as(env, "dev01")
            kb_page.open()
            kb_page.debug_identity("DEV 打开知识库后")

        try:
            with allure.step("2. 先确认身份真的切过来了（否则后面的断言是假阴性）"):
                role = kb_page.current_role()
                assert role == "DEV", f"DEV 账号的角色应为 'DEV'，实际 {role!r}"

            with allure.step("3. DEV 看不到破坏性入口"):
                assert kb_page.is_element_visible(kb_page.BTN_UPLOAD) is False, \
                    "DEV 不应看到上传按钮"
                assert kb_page.is_element_visible(kb_page.COL_ACCESS_LEVEL_HEADER) is False, \
                    "DEV 不应看到「访问权限」列"

            with allure.step("4. DEV 打开这份文件，确认内容已带上 ADMIN 的修改"):
                rows = kb_page.row_files()
                name = SEEDED_FILE or (rows[0] if rows else "")
                if not name:
                    if KB_SEEDED:
                        pytest.fail(
                            "ADMIN 用例报告上传成功，但 DEV 这边看到空列表 —— "
                            "同一份数据两个角色可见性不一致（访问权限选了「全员访问」应可见）"
                        )
                    pytest.skip("知识库没有数据：先跑 test_upload_and_edit_knowledge 造数据")

                assert kb_page.wait_row(name) is True, \
                    f"DEV 列表里看不到 {name}，当前列表：{kb_page.row_files()}"

                text = kb_page.view_file(name)
                assert kb_page.drawer_title().startswith("查看文件："), \
                    f"抽屉标题不对：{kb_page.drawer_title()!r}"
                if KB_SEEDED:
                    assert "UI 自动化追加" in text, \
                        f"DEV 看到的内容没有 ADMIN 的修改（可能读的是缓存）：{text[:120]!r}"
                    print(f"[KB] ✅ DEV 端已看到修改后的内容（{len(text)} 字）")
                kb_page.close_drawer()

                actions = kb_page.row_action_texts(name)
                assert "删除" not in actions, \
                    f"DEV 行内不应有删除按钮，实际：{actions}"
                print(f"[KB] DEV 行内操作 = {actions}")

        finally:
            # 注意：finally 里绝不能 return（会吞掉 try 里的断言失败，用例变成假 PASSED）
            with allure.step("5. 回到 ADMIN 端，删除本轮上传的文件"):
                if not KB_SEEDED or not SEEDED_FILE:
                    print("[KB-CLEANUP] 本轮没有成功上传的文件，跳过删除")
                else:
                    try:
                        login_page.login_as(env, "admin")
                        kb_page.open()
                        kb_page.search(SEEDED_FILE)
                        if kb_page.row_exists(SEEDED_FILE, timeout=10):
                            kb_page.delete_file(SEEDED_FILE)
                            assert kb_page.row_exists(SEEDED_FILE, timeout=0) is False, \
                                f"删除后列表里还有 {SEEDED_FILE}：{kb_page.row_files()}"
                            print(f"[KB-CLEANUP] ✅ ADMIN 已删除 {SEEDED_FILE}")
                        else:
                            print(f"[KB-CLEANUP] 列表里没有 {SEEDED_FILE}，可能已被他人删除")
                    except Exception as e:
                        print(f"[KB-CLEANUP] ⚠️ 删除失败，请手动清理 {SEEDED_FILE}："
                              f"{type(e).__name__}: {e}")


    # ==================================================================
    # 访问权限矩阵（源码 formData.accessLevel：1/2/3）
    #   1 全员访问    员工可见原文，AI 可检索  → DEV/QA 列表能看到、能看正文
    #   2 AI 可检索   员工不可见原文          → DEV/QA 列表看不到
    #   3 仅管理员    员工与 AI 均不可访问    → DEV/QA 列表看不到
    # 三条用例各用一个不同后缀的现成素材（txt/docx/pdf），避免同名被判重：
    # 每条都走「ADMIN 上传 → ADMIN 核标签 → 员工核可见性 → 回 ADMIN 删除」。
    # ==================================================================
    def _run_level_case(self, kb_page, env, login_page, *, suffix: str, level: str,
                        tag: str, employee_visible: bool, expect_vectors: bool,
                        employees=("dev01",)):
        data_file = _kb_file_of(suffix)
        file_name = data_file.name
        uploaded = False

        try:
            with allure.step(f"1. ADMIN 以「{level}」上传 {file_name}"):
                login_page.login_as(env, "admin")
                kb_page.open()
                kb_page.open_upload_dialog()
                kb_page.upload_file(str(data_file), access_level=level)
                uploaded = True
                kb_page.wait_message("上传成功")
                kb_page.search(file_name)
                assert kb_page.wait_row(file_name) is True, \
                    f"上传后列表里没有 {file_name}，当前列表：{kb_page.row_files()}"
                actual = kb_page.get_access_level(file_name)
                assert actual == tag, \
                    f"「访问权限」标签应为「{tag}」，实际「{actual}」（选错档位会让可见性断言全错）"

            with allure.step("2. 查库核对向量：AI 侧到底能不能检索到"):
                total = vec = None
                try:
                    total, vec = _chunk_stats(env, file_name)
                except Exception as e:
                    print(f"[KB][DB] ⚠️ 连库失败，跳过向量断言（不影响 UI 断言）："
                          f"{type(e).__name__}: {e}")
                if total is not None:
                    assert total > 0, \
                        f"库里没有 {file_name} 的分块，上传并没有真正落库"
                    if expect_vectors:
                        assert vec == total, \
                            f"「{level}」的文件应全部带向量，实际 {vec}/{total} 个分块有向量"
                    else:
                        assert vec == 0, \
                            f"「{level}」的文件不该有向量（AI 应检索不到），实际 {vec}/{total} 个"
                    print(f"[KB][DB] {file_name}：分块 {total} 个，带向量 {vec} 个")

            for emp in employees:
                with allure.step(
                    f"3. {emp} 视角：{'应能看到' if employee_visible else '不应看到'} {file_name}"
                ):
                    login_page.login_as(env, emp)
                    kb_page.open()
                    kb_page.search(file_name)
                    seen = kb_page.row_exists(file_name, timeout=5)
                    assert seen is employee_visible, (
                        f"{emp} 查「{file_name}」（权限档位={level}，标签={tag}）时"
                        f"{'看不到' if employee_visible else '看到了'}，"
                        f"当前列表：{kb_page.row_files()}。"
                        "若与预期相反，是后端按 accessLevel 过滤的实现有问题"
                    )
                    # 员工端永远不该出现「访问权限」列，所以读不到标签
                    assert kb_page.is_element_visible(
                        kb_page.COL_ACCESS_LEVEL_HEADER) is False, \
                        f"{emp} 不应看到「访问权限」列"
                    if seen:
                        text = kb_page.view_file(file_name)
                        print(f"[KB] {emp} 打开 {file_name} 正文 {len(text)} 字")
                        assert text.strip(), f"{emp} 打开后正文为空：{text[:120]!r}"
                        kb_page.close_drawer()
                        actions = kb_page.row_action_texts(file_name)
                        assert "删除" not in actions, \
                            f"{emp} 行内不应有删除按钮，实际：{actions}"

        finally:
            # finally 里不写 return（会吞掉断言失败，变成假 PASSED）
            with allure.step("4. 回到 ADMIN 删除这份文件"):
                if not uploaded:
                    print(f"[KB-CLEANUP] {file_name} 未上传成功，跳过删除")
                else:
                    try:
                        login_page.login_as(env, "admin")
                        kb_page.open()
                        kb_page.search(file_name)
                        if kb_page.row_exists(file_name, timeout=10):
                            kb_page.delete_file(file_name)
                            assert kb_page.row_exists(file_name, timeout=0) is False, \
                                f"删除后列表里还有 {file_name}：{kb_page.row_files()}"
                            print(f"[KB-CLEANUP] ✅ 已删除 {file_name}")
                        else:
                            print(f"[KB-CLEANUP] 列表里没有 {file_name}，可能已被删除")
                    except Exception as e:
                        print(f"[KB-CLEANUP] ⚠️ 删除失败，请手动清理 {file_name}："
                              f"{type(e).__name__}: {e}")

    @allure.title("访问权限=全员访问：ADMIN 与员工都能看到并能读正文")
    def test_level_1_all_visible(self, kb_page, env, login_page):
        self._run_level_case(kb_page, env, login_page,
                             suffix=".txt", level="全员访问", tag="全员访问",
                             employee_visible=True, expect_vectors=True,
                             employees=("dev01",))

    @allure.title("访问权限=AI可检索：员工看不到原文，AI 有向量")
    def test_level_2_ai_only(self, kb_page, env, login_page):
        self._run_level_case(kb_page, env, login_page,
                             suffix=".docx", level="AI可检索", tag="AI可检索",
                             employee_visible=False, expect_vectors=True,
                             employees=("dev01",))

    @allure.title("访问权限=仅管理员：DEV 与 QA 均看不到，且没有向量")
    def test_level_3_admin_only(self, kb_page, env, login_page):
        self._run_level_case(kb_page, env, login_page,
                             suffix=".pdf", level="仅管理员", tag="仅管理员",
                             employee_visible=False, expect_vectors=False,
                             employees=("dev01", "qa01"))

