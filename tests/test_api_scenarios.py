"""
Test script to run all 4 scenarios against the live RippleGuard backend.
"""
import requests
import json

def test_all_scenarios():
    base_url = "http://127.0.0.1:8000"
    
    # 1. Health & Status
    status = requests.get(f"{base_url}/api/status").json()
    assert "total_nodes" in status, "Status must include total_nodes"
    print(f"[OK] System Status: {status['mode']} | {status['total_nodes']} nodes, {status['total_edges']} edges")
    
    # 2. Scenarios
    scenarios = requests.get(f"{base_url}/api/scenarios").json()
    assert len(scenarios) >= 4, "Must have at least 4 scenarios"
    
    for sc in scenarios:
        pr_id = sc["pr_id"]
        res = requests.post(f"{base_url}/api/analyze", json=sc).json()
        assert "risk_analysis" in res, f"Analysis failed for {pr_id}"
        
        score = res["risk_analysis"]["score"]
        tier = res["risk_analysis"]["tier"]
        tests_selected = len(res["action_results"]["test_selection"]["selected_tests"])
        gate = res["action_results"]["gate_decision"]["gate_status"]
        traces_count = len(res["agent_traces"])
        
        print(f"[OK] Scenario {pr_id} ('{sc['title'][:32]}...'):")
        print(f"     Risk Score: {score}/100 [{tier}]")
        print(f"     Selected Tests: {tests_selected}")
        print(f"     Gate Decision: {gate}")
        print(f"     Agent Trace Steps: {traces_count}")
        print(f"     Execution Duration: {res['execution_duration_ms']}ms")

    # 3. Test Cypher query
    cypher_res = requests.post(f"{base_url}/api/query/cypher", json={"cypher": "MATCH (m:Microservice) RETURN m.name"}).json()
    assert "rows" in cypher_res, "Cypher query must return rows"
    print(f"[OK] Cypher Query Execution: {len(cypher_res['rows'])} rows returned in {cypher_res['duration_ms']}ms")

    # 4. Safe Gate Decision
    gate_res = requests.post(f"{base_url}/api/gate/decision", json={
        "pr_id": "PR-104",
        "session_id": "sess_test",
        "decision": "APPROVED",
        "approver": "Sarah Chen",
        "notes": "Verified dual-write compatibility window"
    }).json()
    assert gate_res["status"] == "DECISION_COMMITTED"
    print(f"[OK] Safe Gate Approval Submission: {gate_res['status']}")

    # 5. Cross-Session Memory Check
    mem_res = requests.get(f"{base_url}/api/memory").json()
    assert mem_res["count"] > 0, "Must have recorded memories in FalkorDB"
    print(f"[OK] FalkorDB Cross-Session Memories: {mem_res['count']} memories retrieved from graph")

if __name__ == "__main__":
    test_all_scenarios()
