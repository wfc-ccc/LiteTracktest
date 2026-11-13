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
    pytest.param("dev_token", 403, id="dev-forbidden"),
    pytest.param("pm_token", 200, id="pm-allowed"),
]


@allure.feature("任务管理")
@allure.story("审核权限")
class TestTaskAuditPermission:
    @allure.title("审核接口权限矩阵：{token_name} 的业务码应为 {expected_code}")
    @pytest.mark.parametrize("token_name,expected_code", _CASES)
    def test_audit_permission_matrix(self, request, task_api, setup_task, audit_payload, token_name, expected_code):
        token = request.getfixturevalue(token_name)
        with allure.step(f"使用 {token_name} 调用 PATCH /api/tasks/{{id}}/audit"):
            response = task_api.audit(
                token,
                setup_task,
                audit_result=audit_payload["auditResult"],
                audit_reason=audit_payload["auditReason"],
            )

        with allure.step("断言 HTTP 200，并按角色断言业务码"):
            assert response.status_code == 200, response.text
            body = response.json()
            allure.attach(
                response.text,
                name="audit-response",
                attachment_type=allure.attachment_type.JSON,
            )
            assert "code" in body, body
            # DEV：业务码必须不是成功，且与 RoleAspect 的 403 一致
            if expected_code != 200:
                assert body["code"] != 200, body
            assert body["code"] == expected_code, body
