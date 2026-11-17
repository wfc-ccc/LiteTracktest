"""任务审核权限矩阵。
后端 GlobalExceptionHandler 把 BusinessException 包成 Result，HTTP 状态码仍是 200。
DEV 调用审核会被 RoleAspect 拦截，body.code = 403。
PM 只有在任务处于 PENDING_REVIEW 时审核通过才会得到 body.code = 200，
因此 setup_task 会把新建任务推进到待审核。
"""
from __future__ import annotations
import allure
import pytest

pytestmark = pytest.mark.api

_CASES = [
    pytest.param("dev_client", 403, id="dev-forbidden"),
    pytest.param("pm_client", 200, id="pm-allowed"),
]


@allure.feature("任务管理")
@allure.story("审核权限")
class TestTaskAuditPermission:
    @allure.title("审核接口权限矩阵：{token_name} 的业务码应为 {expected_code}")
    @pytest.mark.parametrize("token_name,expected_code", _CASES)
    def test_audit_permission_matrix(self, request, env, setup_task, audit_payload, token_name, expected_code):
        client = request.getfixturevalue(token_name)
        body = {
            "auditResult": audit_payload["audit_pass"]["auditResult"],
            "auditReason": audit_payload["audit_pass"]["auditReason"],
        }
        path = f"{env['api_base_url']}/api/tasks/{setup_task}/audit"

        with allure.step(f"使用 {token_name} 调用 PATCH /api/tasks/{{id}}/audit"):
            response = client.request("PATCH", path, json=body)

        with allure.step("断言 HTTP 200，并按角色断言业务码"):
            assert response.status_code == 200, f"HTTP状态码异常：{response.text}"
            resp_body = response.json()

            allure.attach(
                response.text,
                name="audit-response",
                attachment_type=allure.attachment_type.JSON,
            )
            assert "code" in resp_body, f"返回结构缺少code字段：{resp_body}"
            if expected_code != 200:
                assert resp_body["code"] != 200, f"预期业务码非200，实际返回 {resp_body}"
            assert resp_body["code"] == expected_code, f"业务码不匹配，预期：{expected_code}，返回：{resp_body}"
