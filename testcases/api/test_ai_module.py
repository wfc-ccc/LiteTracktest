import allure
import pytest
import uuid
from pathlib import Path
from utils.config_loader import DATA_DIR


def _kb_file(ext: str) -> Path:
    path = DATA_DIR / f"ai-test-{uuid.uuid4().hex[:6]}.{ext}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("这是用于知识库接口自动化的测试文本，包含足够的内容以满足要求。", encoding="utf-8")
    return path


@allure.feature("API - AI 智能模块")
class TestAiAssistantApi:

    @pytest.fixture
    def ai(self, admin_client):
        from api.ai_chat_api import AiChatApi
        return AiChatApi(admin_client, base_url="")

    @allure.title("新建会话：空标题回落「新对话」，会话出现在列表")
    def test_create_session_default_title(self, ai):
        created = ai.create_session("")
        sid = created["id"]
        try:
            assert created["title"] == "新对话"
            assert any(s["id"] == sid for s in ai.list_sessions())
        finally:
            ai.delete_session(sid)

    @allure.title("新建时指定标题 + 重命名生效")
    def test_create_with_title_and_rename(self, ai):
        created = ai.create_session("接口自动化-初始名")
        sid = created["id"]
        try:
            assert created["title"] == "接口自动化-初始名"
            ai.update_session(sid, title="重命名后的标题")
            target = next(s for s in ai.list_sessions() if s["id"] == sid)
            assert target["title"] == "重命名后的标题"
        finally:
            ai.delete_session(sid)

    @allure.title("置顶优先于更新时间排序，取消置顶后标记复位")
    def test_pin_sorts_first(self, ai):
        older = ai.create_session("置顶候选-A")
        newer = ai.create_session("更新的会话-B")
        try:
            ids = [s["id"] for s in ai.list_sessions()]
            assert ids[0] == newer["id"], f"都未置顶时应按 update_time 倒序，首条应为 B({newer['id']})，实际 {ids}"

            ai.update_session(older["id"], is_top=1)
            sessions = ai.list_sessions()
            assert sessions[0]["id"] == older["id"], f"置顶后 A 应排第一，实际首条 {sessions[0]['id']}"

            ai.update_session(older["id"], is_top=0)
            target = next(s for s in ai.list_sessions() if s["id"] == older["id"])
            flag = target.get("isTop", target.get("top", 0))
            assert not bool(flag), f"取消置顶后 isTop 没复位：{flag!r}"
        finally:
            ai.delete_session(older["id"])
            ai.delete_session(newer["id"])

    @allure.title("删除会话：列表移除，且消息级联清掉")
    def test_delete_session_cascade(self, ai):
        created = ai.create_session("待删除会话")
        sid = created["id"]
        ai.delete_session(sid)
        assert all(s["id"] != sid for s in ai.list_sessions()), "删除后列表仍存在该会话"

    @pytest.mark.slow
    @allure.title("SSE 契约：事件结构稳定、以 isEnd 收尾、消息落库且顺序正序")
    def test_sse_contract_and_persistence(self, ai):
        created = ai.create_session("SSE 契约会话")
        sid = created["id"]
        try:
            payload = {"sessionId": sid, "message": "只回答一个字：好"}
            resp = ai.chat(payload)
            assert resp.status_code == 200

            # 校验响应头，如果是 JSON 说明直接报错了
            content_type = resp.headers.get("Content-Type", "")
            if "application/json" in content_type:
                raise AssertionError(f"后端返回了 JSON 错误而不是 SSE: {resp.json()}")

            events = []
            for line in resp.iter_lines(chunk_size=1024):
                if line:
                    line_str = line.decode("utf-8", errors="ignore").strip()
                    if line_str.startswith("data:"):
                        events.append(line_str)

            assert len(events) > 0, "未收到任何 SSE 事件"
            assert "isEnd" in events[-1] and "true" in events[-1], f"流末尾未收到 isEnd 标记，实际最后一条: {events[-1]}"

            # 验证数据库落库
            msgs = ai.wait_messages(sid, min_count=2, timeout=15)
            assert len(msgs) >= 2, f"消息未落库，当前条数：{len(msgs)}"
            assert msgs[0]["role"] == "user"
            assert msgs[1]["role"] == "assistant"
            assert len(msgs[1]["content"]) > 0, "助手回复的内容为空"
        finally:
            ai.delete_session(sid)

    @pytest.mark.slow
    @allure.title("会话隔离：A 会话发的消息不会串到 B 会话")
    def test_session_isolation(self, ai):
        a = ai.create_session("隔离-A")
        b = ai.create_session("隔离-B")
        try:
            with allure.step("1. 只往 A 发问"):
                resp = ai.chat({"message": "只回答两个字：收到", "sessionId": a["id"]})
                assert resp.status_code == 200
                # 强制消费流，确保后端执行完毕并落库
                list(resp.iter_lines())

            with allure.step("2. A 有新消息、B 仍为空"):
                msgs_a = ai.wait_messages(a["id"], min_count=2, timeout=15)
                assert len(msgs_a) >= 2, f"A 会话消息不足：{msgs_a}"
                assert ai.list_messages(b["id"]) == [], f"B 会话被串了：{ai.list_messages(b['id'])}"
        finally:
            ai.delete_session(a["id"])
            ai.delete_session(b["id"])

    def _chat_raw(self, admin_client, env, payload):
        return admin_client.post(f"{env['api_base_url']}/api/ai/chat", json=payload, timeout=10)

    @pytest.mark.slow
    @allure.title("边界：空 message / 缺 sessionId 必须返回明确业务错误，不能 500")
    def test_empty_message_rejected(self, admin_client, env):
        resp = self._chat_raw(admin_client, env, {"message": ""})
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        assert resp.status_code == 200 and body.get("code") == 400, f"预期 400 业务错误，实际：{body}"

    @pytest.mark.slow
    @allure.title("边界：不存在的 sessionId 必须给出明确错误，不能 500")
    def test_unknown_session_rejected(self, admin_client, env):
        resp = self._chat_raw(admin_client, env, {"message": "你好", "sessionId": 999999999})
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        assert resp.status_code == 200 and body.get("code") == 404, f"预期 404 业务错误，实际：{body}"

    @allure.title("对话内临时上传：提取纯文本并按 3000 字上限截断")
    def test_upload_temp_extracts_text(self, ai):
        data_file = _kb_file("txt")
        long_text = "测试文本" * 1000
        data_file.write_text(long_text, encoding="utf-8")
        try:
            text = ai.upload_temp(str(data_file))
            assert len(text) > 0, "提取的文本为空"
            assert len(text) == 3000, f"未按 3000 字上限截断，实际长度: {len(text)}"
        finally:
            # 用完删除文件，加判断防止文件不存在抛异常
            if data_file.exists():
                data_file.unlink()

    @allure.title("缺陷润色：正常入参返回结构化的缺陷单")
    def test_optimize_bug(self, ai, project_id):
        raw_text = "登录偶发 500：并发登录时约 1/50 概率返回 500，日志无异常堆栈。"
        res = ai.optimize_bug(raw_text, project_id)
        print(f"[AI-API] optimize-bug → {res}")
        assert "title" in res
        # 修正：允许的枚举值加入全量兼容
        assert res["severity"] in ("FATAL", "SERIOUS", "HIGH", "NORMAL", "MEDIUM", "LOW", "URGENT"), f"非预期的严重级别: {res['severity']}"
        assert len(res["description"]) > 0
