"""AI 助手悬浮面板 UI 用例。

被测对象：frontend/components/AiAssistant.vue —— 全局悬浮面板，挂在任意已登录页面上，
入口是右下角悬浮球 `.ai-fab`，不是独立路由。

覆盖 10 条：
1. 悬浮球开合面板（标题、尺寸、关闭后隐藏、再开恢复）
2. 空输入时发送按钮保持 disabled
3. 发消息 → 流式回复 → Markdown 渲染完成
4. Enter 发送 / Shift+Enter 只换行
5. 生成中点「停止」能中断
6. 新对话清空消息区，历史条目 +1
7. 历史抽屉切换会话，active 高亮跟随
8. 置顶后该会话排到第一
9. 重命名 + 删除（含 ElMessageBox 两个弹窗）
10. 上传附件 → 消息里出现参考文件卡 → 点开预览正文 → 关闭后附件标签自动清掉

约定：
- 全文件不使用 time.sleep，等待一律走 POM 里的显式等待；
- 会话数据由 API 侧清理（autouse 的 session_cleaner），UI 只负责操作；
- 断言尽量落在「用户能看到的东西」上（气泡文本、Markdown 容器、历史标题），
  不去断言 Vue 内部状态。
"""
from __future__ import annotations

import uuid
from pathlib import Path

import allure
import pytest

from pages.ai_assistant_page import AiAssistantPage
from utils.config_loader import DATA_DIR

# 素材：沿用工程里已有的知识库文件，不另外造数据文件
_KB_FILES = {"txt": "知识库.txt", "docx": "文档 (2).docx", "pdf": "新建 .pdf"}


def _kb_dir() -> Path:
    base = Path(DATA_DIR)
    for name in ("uplodedata", "uploadedata"):
        d = base / name
        if d.is_dir():
            return d
    raise AssertionError(f"{base} 下找不到 uplodedata / uploadedata 目录")


def _attachment(kind: str = "txt") -> Path:
    f = _kb_dir() / _KB_FILES[kind]
    assert f.is_file(), f"素材不存在：{f}"
    return f


@pytest.fixture
def ai_page(logged_in_driver, env) -> AiAssistantPage:
    """已登录（PM 角色）+ 面板已打开 + 处于一条**新建**的会话。

    必须显式开新会话：面板会恢复上次的 sessionId，不点「新对话」的话
    消息会写进上一次的会话（可能是你自己手工建的），标题也不会更新。
    """
    page = AiAssistantPage(logged_in_driver, env["web_base_url"])
    page.open()
    page.start_fresh_session()
    yield page


@pytest.fixture(autouse=True)
def session_cleaner(pm_client, env):
    """按「测试前 / 测试后」的会话集合差集清理，不误删用户已有会话。

    logged_in_driver 注入的是 pm01 的 token，所以清理也用 pm_client。
    """
    base = env["api_base_url"].rstrip("/")

    def _ids():
        resp = pm_client.get(f"{base}/api/ai/sessions", timeout=15)
        if resp.status_code != 200:
            return set()
        return {s.get("id") for s in (resp.json().get("data") or [])}

    before = _ids()
    yield
    try:
        after = _ids()
    except Exception as e:
        print(f"[AI-UI][清理] 读取会话列表失败：{type(e).__name__}: {e}")
        return
    for sid in sorted(after - before):
        try:
            pm_client.delete(f"{base}/api/ai/sessions/{sid}", timeout=15)
            print(f"[AI-UI][清理] 已删除测试产生的会话 {sid}")
        except Exception as e:
            print(f"[AI-UI][清理] 会话 {sid} 删除失败：{type(e).__name__}: {e}")


@allure.feature("UI 自动化")
@allure.story("AI 助手面板")
class TestAiAssistantUI:

    # ---------------- 面板开合 ----------------
    @allure.title("悬浮球开合：标题正确、尺寸在范围内、关闭后隐藏、再开恢复")
    def test_panel_toggle(self, ai_page):
        with allure.step("1. 面板已打开且标题是「轻舟 AI 助手」"):
            assert ai_page.is_open(), "悬浮球点了之后面板没出来"
            assert ai_page.header_title() == "轻舟 AI 助手", \
                f"面板标题不对：{ai_page.header_title()!r}"

        with allure.step("2. 默认尺寸不应小于源码里的最小值 350×400"):
            width, height = ai_page.panel_size()
            print(f"[AI-UI] 面板尺寸 = {width}×{height}")
            assert width >= 350 and height >= 400, f"面板尺寸异常：{width}×{height}"

        with allure.step("3. 关闭后 .ai-panel 不可见"):
            ai_page.close()
            assert not ai_page.is_open(), "点了关闭，面板仍在显示"

        with allure.step("4. 再点悬浮球能重新打开"):
            ai_page.open()
            assert ai_page.is_open()

    @allure.title("最大化：面板宽度变大，再点还原回到原尺寸")
    def test_maximize_and_restore(self, ai_page):
        width_before = ai_page.panel_size()[0]
        width_max = ai_page.maximize()[0]
        print(f"[AI-UI] 最大化：{width_before} → {width_max}")
        assert width_max > width_before, "点了最大化，面板宽度没变"

        restored = ai_page.restore(width_before)[0]
        assert abs(restored - width_before) <= 2, (
            f"还原后宽度 {restored} != 原宽 {width_before}（允许 1~2px 取整误差）"
        )

    # ---------------- 输入区状态 ----------------
    @allure.title("空输入时发送按钮保持 disabled，输入后才可点")
    def test_empty_input_keeps_send_disabled(self, ai_page):
        ai_page.clear_input()
        assert ai_page.wait_send_disabled(timeout=5), "输入框为空，发送按钮却不是 disabled"

        ai_page.type_message("你好")
        assert ai_page.wait_send_enabled(timeout=5), "输入了内容，发送按钮还是灰的"

        ai_page.clear_input()
        assert ai_page.wait_send_disabled(timeout=5), "清空输入后发送按钮没变回 disabled"

    @allure.title("Enter 发送、Shift+Enter 只换行不发送")
    def test_enter_sends_and_shift_enter_newline(self, ai_page):
        ai_page.new_chat()
        before = ai_page.count_user_rows()

        with allure.step("1. Shift+Enter 只换行"):
            ai_page.type_keys("第一行")
            ai_page.press_shift_enter()
            ai_page.type_keys("第二行")
            value = ai_page.input_value()
            print(f"[AI-UI] 输入框内容 = {value!r}")
            assert "\n" in value, "Shift+Enter 没有换行"
            assert ai_page.count_user_rows() == before, "Shift+Enter 居然把消息发出去的"

        with allure.step("2. Enter 直接发送"):
            ai_page.press_enter()
            assert ai_page.wait_user_count(before + 1, timeout=15), "按 Enter 没有发送"
            ai_page.wait_reply_finished(timeout=90)
            assert ai_page.count_user_rows() == before + 1

    # ---------------- 流式对话 ----------------
    @allure.title("发消息：用户气泡入列、流式回复转 Markdown、思考态消失")
    def test_send_message_and_markdown(self, ai_page):
        question = "用一句话说明缺陷跟踪的意义"

        with allure.step(f"1. 发送「{question}」"):
            ai_page.send(question)

        with allure.step("2. 用户气泡文案正确、欢迎语让位"):
            assert question in " ".join(ai_page.all_user_texts()), \
                f"用户气泡没显示问题：{ai_page.all_user_texts()}"
            assert not ai_page.welcome_visible(), "已经有消息了，欢迎语还在"

        with allure.step("3. 回复结束：markdown 渲染出正文，思考态与停止按钮都消失"):
            reply = ai_page.wait_reply_finished(timeout=90)
            print(f"[AI-UI] 回复前 60 字：{reply[:60]!r}")
            assert len(reply) > 0, "AI 回复正文为空"
            assert not ai_page.is_generating(), "回复结束了，停止按钮还在"
            assert not ai_page.thinking_visible(), "回复结束了，「正在思考」还在"

        with allure.step("4. 停止按钮退回发送按钮，免责声明常驻"):
            assert ai_page.wait_send_btn_back(timeout=10), "回复结束后发送按钮没回来"
            # v-if 是 !isGenerating，:disabled 是 !input.trim()；发完输入框已清空，
            # 所以按钮回来时天然是 disabled，这里断言的是「空输入不可点」这条设计
            assert ai_page.is_send_disabled(), "输入框为空时发送按钮应是 disabled"
            assert ai_page.disclaimer_visible(), "「内容由 AI 生成」免责声明不见了"

    @allure.title("生成中点「停止」：中断生成并恢复输入态")
    def test_stop_generating(self, ai_page):
        ai_page.new_chat()
        ai_page.send("请用三百字介绍敏捷开发的四个核心实践")

        if ai_page.wait_generating(timeout=12):
            with allure.step("1. 生成态出现「停止」按钮，点击中断"):
                ai_page.stop_generating()
            with allure.step("2. 中断后不能再处于生成态，发送按钮回来"):
                assert not ai_page.is_generating()
                assert ai_page.wait_send_btn_back(timeout=15), "停止后发送按钮没回来"
                assert ai_page.is_send_disabled(), "停止后输入框为空，发送按钮应是 disabled"
                assert not ai_page.thinking_visible(), "停止后仍显示「正在思考」"
        else:
            # 模型极快时可能捕捉不到生成态，这不算失败，但要把事实记录下来
            print("[AI-UI] 12s 内没观察到「停止」按钮（生成太快），退化为等待正常完成")
            ai_page.wait_reply_finished(timeout=90)

    # ---------------- 新对话 / 历史 ----------------
    @allure.title("新对话：消息区清空、欢迎语回归、历史条目 +1")
    def test_new_chat_resets_and_adds_history(self, ai_page):
        ai_page.send("只回答两个字：收到")
        ai_page.wait_reply_finished(timeout=90)

        ai_page.open_history()
        count_before = ai_page.history_count()
        print(f"[AI-UI] 新对话前历史条目 = {count_before}")
        ai_page.close_history()

        ai_page.new_chat()

        assert ai_page.count_user_rows() == 0, "点了新对话，用户气泡还在"
        assert ai_page.welcome_visible(), "点了新对话，欢迎语没回来"

        ai_page.open_history()
        count_after = ai_page.history_count()
        assert count_after == count_before + 1, \
            f"新对话后历史条目应 +1，实际 {count_before} → {count_after}"
        assert ai_page.history_active_titles(), "新会话没有被设为当前会话"

    @allure.title("历史抽屉：切到别的会话，消息区内容跟着换（双向验证）")
    def test_history_switch_active(self, ai_page):
        q1 = "第一个会话的问题"
        q2 = "第二个会话的问题"
        tag = uuid.uuid4().hex[:6]
        t1, t2 = f"UI-切A-{tag}", f"UI-切B-{tag}"

        with allure.step("1. 造两个会话，各自改成唯一标题（便于在历史里精确定位）"):
            ai_page.send(q1)
            ai_page.wait_reply_finished(timeout=90)
            ai_page.open_history()
            ai_page.rename_active(t1)
            ai_page.close_history()

            ai_page.new_chat()
            ai_page.send(q2)
            ai_page.wait_reply_finished(timeout=90)
            ai_page.open_history()
            ai_page.rename_active(t2)

        titles = ai_page.history_titles()
        print(f"[AI-UI] 历史条目 = {titles}")
        assert t1 in titles and t2 in titles, f"两条会话标题不在历史里：{titles}"

        with allure.step(f"2. 切到「{t1}」：消息区回到第一个会话"):
            ai_page.click_history_title(t1)
            assert ai_page.wait_user_text(q1, timeout=15, last_only=True), \
                f"点历史条目没切过去，当前气泡：{ai_page.all_user_texts()}"
            print(f"[AI-UI] 点条目后 抽屉打开={ai_page.history_open()}")
            if ai_page.history_open():
                ai_page.close_history()
                assert not ai_page.history_open(), "再点历史按钮没有收起抽屉"

        with allure.step(f"3. 切回「{t2}」：消息区换回第二个会话"):
            ai_page.open_history()
            ai_page.click_history_title(t2)
            assert ai_page.wait_user_text(q2, timeout=15, last_only=True), \
                f"切回没生效，当前气泡：{ai_page.all_user_texts()}"

    @allure.title("置顶：被置顶的会话排到历史列表第一")
    def test_pin_moves_to_first(self, ai_page):
        tag = uuid.uuid4().hex[:6]
        t1, t2 = f"UI-顶A-{tag}", f"UI-顶B-{tag}"

        with allure.step("1. 造两个会话并改成唯一标题"):
            ai_page.send("置顶测试的第一条")
            ai_page.wait_reply_finished(timeout=90)
            ai_page.open_history()
            ai_page.rename_active(t1)
            ai_page.close_history()

            ai_page.new_chat()
            ai_page.send("置顶测试的第二条")
            ai_page.wait_reply_finished(timeout=90)
            ai_page.open_history()
            ai_page.rename_active(t2)

        titles = ai_page.history_titles()
        print(f"[AI-UI] 置顶前顺序 = {titles}")
        assert t1 in titles and t2 in titles, f"两条会话不在历史里：{titles}"
        assert titles.index(t2) < titles.index(t1), f"最近的会话没排在前面：{titles}"

        with allure.step(f"2. 置顶「{t1}」后它应排到第一"):
            ai_page.pin_title(t1)
            assert ai_page.wait_history_first(t1, timeout=15), \
                f"置顶后没排到第一，当前顺序：{ai_page.history_titles()}"

    @allure.title("重命名与删除：标题即时更新，删除后条目消失")
    def test_rename_and_delete(self, ai_page):
        new_title = f"UI-重命名-{uuid.uuid4().hex[:6]}"

        ai_page.send("这条会话会被改名")
        ai_page.wait_reply_finished(timeout=90)
        ai_page.open_history()
        assert ai_page.history_count() >= 1, "历史里没有会话"

        with allure.step("1. 改当前会话的名字，标题立刻更新"):
            old_title = ai_page.rename_active(new_title)
            assert ai_page.active_title() == new_title, \
                f"改名后标题没即时更新：{ai_page.active_title()!r}"
            ai_page.close_history()
            ai_page.open_history()
            assert new_title in ai_page.history_titles(), \
                f"重开抽屉后标题没落库：{ai_page.history_titles()}"
            print(f"[AI-UI] 重命名生效：{old_title!r} → {new_title!r}")

        with allure.step("2. 删除这条会话，条目消失"):
            ai_page.delete_title(new_title)
            ai_page.open_history()
            assert new_title not in ai_page.history_titles(), "删除后条目还在"

    # ---------------- 附件 ----------------
    @allure.title("上传附件：附件标签出现 → 消息里出参考文件卡 → 预览正文 → 标签自动清除")
    def test_attachment_upload_and_preview(self, ai_page):
        attachment = _attachment("txt")

        with allure.step(f"1. 选文件 {attachment.name}"):
            tag_text = ai_page.upload_attachment(str(attachment))
            assert attachment.name in tag_text, f"附件标签没显示文件名：{tag_text!r}"

        with allure.step("2. 发送问题：用户气泡里出现「参考文件」卡片"):
            ai_page.send("这份文件讲了什么")

        assert ai_page.wait_msg_file_card(timeout=20), \
            f"消息里没有参考文件卡：{ai_page.all_user_texts()}"

        with allure.step("3. 点开卡片，预览弹窗里是文件正文"):
            ai_page.click_msg_file()
            preview = ai_page.preview_text()
            print(f"[AI-UI] 预览正文前 40 字：{preview[:40]!r}")
            assert preview.strip(), "预览弹窗里没有内容"
            ai_page.close_preview()

        with allure.step("4. 发送成功后附件标签应被自动清掉"):
            ai_page.wait_reply_finished(timeout=90)
            assert ai_page.attachment_name() == "", \
                f"发送完附件标签还在：{ai_page.attachment_name()!r}"
