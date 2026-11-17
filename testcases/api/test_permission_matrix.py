import allure
import pytest
from utils.config_loader import load_yaml

def get_matrix_cases():
    config = load_yaml("permission_matrix.yaml")
    endpoints = config["endpoints"]
    cases = []
    for row in config["matrix"]:
        for ep_name, expected_code in row["expected"].items():
            cases.append({
                "id": f"{row['role']}_{ep_name}",
                "role": row["role"],
                "account": row["account"],
                "client_fixture": row["client_fixture"],
                "ep_info": endpoints[ep_name],
                "expected_code": expected_code
            })
    return cases

@allure.feature("API - 权限矩阵")
class TestPermissionMatrix:

    @allure.title("{case[role]} 角色访问 {case[ep_info][label]} - 期望 {case[expected_code]}")
    @pytest.mark.parametrize("case", get_matrix_cases(), ids=lambda c: c["id"])
    def test_sensitive_endpoints(self, case, request, env, login):
        client = request.getfixturevalue(case["client_fixture"])
        
        # 准备前置状态任务 (TODO 或 PENDING_REVIEW)
        pre_state = case["ep_info"]["pre_state"]
        task_id = request.getfixturevalue("todo_task_id" if pre_state == "TODO" else "setup_task")

        # 构造请求
        path = case["ep_info"]["path"].replace("{task_id}", str(task_id))
        method = case["ep_info"]["method"]
        body = case["ep_info"].get("body")
        
        if body and "assigneeId" in body:
            body["assigneeId"] = login("dev01")["user"]["id"]

        # 发请求
        response = client.request(method, path, json=body)
        assert response.status_code == 200
        assert response.json().get("code") == case["expected_code"]