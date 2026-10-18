"""
RippleGuard Multi-Agent Engine.
Contains Investigator Agent, Risk Analyst Agent, and Action Agent.
The agents use FalkorDB through MCP tools to investigate, reason, and act on connected data.
"""
import uuid
import time
import logging
from typing import Dict, List, Any, Optional
from backend.mcp_tools import get_mcp_registry

logger = logging.getLogger("rippleguard.agents")

class InvestigatorAgent:
    """
    Investigator Agent:
    Uses FalkorDB multi-hop queries and graph traversals to trace direct and transitive blast radius.
    """
    def __init__(self, mcp):
        self.mcp = mcp
        self.role = "Investigator Agent"

    def investigate(self, pr_data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        trace_logs = []
        start_t = time.time()
        
        pr_id = pr_data.get("pr_id", "PR-UNKNOWN")
        changed_symbols = pr_data.get("changed_symbols", [])
        
        trace_logs.append({
            "agent": self.role,
            "phase": "INGEST_PR",
            "message": f"Analyzing change request {pr_id}: '{pr_data.get('title')}' with {len(changed_symbols)} seed symbols.",
            "data": {"pr_id": pr_id, "seed_symbols": changed_symbols}
        })

        # Step 1: Trace multi-hop blast radius in FalkorDB
        trace_logs.append({
            "agent": self.role,
            "phase": "MCP_TOOL_CALL",
            "message": "Invoking MCP tool 'trace_blast_radius' on FalkorDB graph (max_depth=4)...",
            "tool": "trace_blast_radius",
            "arguments": {"seed_node_ids": changed_symbols, "max_depth": 4}
        })

        blast_result = self.mcp.invoke_tool("trace_blast_radius", {
            "seed_node_ids": changed_symbols,
            "max_depth": 4
        })

        # Categorize discovered nodes
        nodes = blast_result.get("nodes", [])
        services = [n for n in nodes if n.get("label") == "Microservice"]
        apis = [n for n in nodes if n.get("label") == "ApiEndpoint"]
        tables = [n for n in nodes if n.get("label") == "DbTable"]
        columns = [n for n in nodes if n.get("label") == "DbColumn"]
        workflows = [n for n in nodes if n.get("label") == "Workflow"]

        trace_logs.append({
            "agent": self.role,
            "phase": "DISCOVERY_COMPLETE",
            "message": f"FalkorDB graph traversal discovered {len(nodes)} impacted nodes across {len(services)} services, {len(apis)} APIs, {len(tables)} DB tables, and {len(workflows)} workflows.",
            "data": {
                "impacted_services": [s.get("name") for s in services],
                "impacted_apis": [a.get("name") for a in apis],
                "impacted_tables": [t.get("name") for t in tables],
                "impacted_workflows": [w.get("name") for w in workflows]
            }
        })

        return {
            "blast_result": blast_result,
            "services": services,
            "apis": apis,
            "tables": tables,
            "columns": columns,
            "workflows": workflows,
            "trace_logs": trace_logs,
            "duration_ms": round((time.time() - start_t) * 1000, 2)
        }


class RiskAnalystAgent:
    """
    Risk Analyst Agent:
    Uses graph algorithms, centrality metrics, historical incident matching, and ADR governance
    to calculate an explainable, multi-factor risk score with concrete evidence paths.
    """
    def __init__(self, mcp):
        self.mcp = mcp
        self.role = "Risk Analyst Agent"

    def analyze_risk(self, pr_data: Dict[str, Any], investigation: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        trace_logs = []
        start_t = time.time()
        
        blast = investigation["blast_result"]
        blast_node_ids = [n["id"] for n in blast.get("nodes", [])]
        seed_symbols = pr_data.get("changed_symbols", [])

        # Step 1: Calculate graph metrics (centrality)
        trace_logs.append({
            "agent": self.role,
            "phase": "MCP_TOOL_CALL",
            "message": "Invoking MCP tool 'calculate_graph_metrics' to assess topological vulnerability...",
            "tool": "calculate_graph_metrics",
            "arguments": {"node_ids": blast_node_ids[:10]}
        })
        metrics_res = self.mcp.invoke_tool("calculate_graph_metrics", {"node_ids": blast_node_ids})
        metrics = metrics_res.get("metrics", {})

        # Step 2: Audit historical incidents and ADRs in FalkorDB
        trace_logs.append({
            "agent": self.role,
            "phase": "MCP_TOOL_CALL",
            "message": "Invoking MCP tool 'audit_incidents_and_adrs' against FalkorDB historical memory...",
            "tool": "audit_incidents_and_adrs",
            "arguments": {"blast_node_ids": blast_node_ids}
        })
        audit_res = self.mcp.invoke_tool("audit_incidents_and_adrs", {"blast_node_ids": blast_node_ids})
        incidents = audit_res.get("incidents", [])
        adrs = audit_res.get("adrs", [])

        # Step 3: Find explainable evidence paths
        explainable_paths = []
        primary_seed = seed_symbols[0] if seed_symbols else None
        
        # Connect to Tier-0 workflows
        for wf in investigation["workflows"]:
            if "Tier-0" in wf.get("tier", "") and primary_seed:
                path_info = self.mcp.invoke_tool("get_explainable_paths", {
                    "source_id": primary_seed,
                    "target_id": wf["id"]
                })
                explainable_paths.extend(path_info.get("paths", []))

        # Connect to prior incidents
        for inc_wrapper in incidents:
            inc_node = inc_wrapper["incident"]
            if primary_seed:
                path_info = self.mcp.invoke_tool("get_explainable_paths", {
                    "source_id": primary_seed,
                    "target_id": inc_node["id"]
                })
                explainable_paths.extend(path_info.get("paths", []))

        # Step 4: Multi-Factor Risk Score Calculation
        score_breakdown = {
            "workflow_criticality": 0,
            "incident_history": 0,
            "blast_reach": 0,
            "adr_governance": 0
        }

        # 4a. Workflow criticality (max 30 pts)
        has_tier0 = any("Tier-0" in w.get("tier", "") for w in investigation["workflows"])
        has_tier1 = any("Tier-1" in w.get("tier", "") for w in investigation["workflows"])
        if has_tier0:
            score_breakdown["workflow_criticality"] = 30
        elif has_tier1:
            score_breakdown["workflow_criticality"] = 18
        elif investigation["workflows"]:
            score_breakdown["workflow_criticality"] = 8

        # 4b. Historical incidents (max 25 pts)
        has_p1 = any(i["incident"].get("severity") == "P1" for i in incidents)
        has_p2 = any(i["incident"].get("severity") == "P2" for i in incidents)
        if has_p1:
            score_breakdown["incident_history"] = 25
        elif has_p2:
            score_breakdown["incident_history"] = 16
        elif incidents:
            score_breakdown["incident_history"] = 8

        # 4c. Blast reach (max 25 pts)
        num_services = len(investigation["services"])
        num_apis = len(investigation["apis"])
        reach_points = min(25, (num_services * 7) + (num_apis * 4) + (len(investigation["tables"]) * 5))
        score_breakdown["blast_reach"] = reach_points

        # 4d. ADR governance & sensitive data (max 20 pts)
        has_pci_table = any("PCI" in t.get("classification", "") for t in investigation["tables"])
        has_adr_rules = len(adrs) > 0
        adr_points = 0
        if has_pci_table:
            adr_points += 12
        if has_adr_rules:
            adr_points += 8
        score_breakdown["adr_governance"] = min(20, adr_points)

        total_risk_score = sum(score_breakdown.values())
        total_risk_score = min(100, max(0, total_risk_score))

        if total_risk_score >= 75:
            risk_tier = "CRITICAL"
        elif total_risk_score >= 50:
            risk_tier = "HIGH"
        elif total_risk_score >= 25:
            risk_tier = "MEDIUM"
        else:
            risk_tier = "LOW"

        trace_logs.append({
            "agent": self.role,
            "phase": "RISK_CALCULATION_COMPLETE",
            "message": f"Computed explainable Risk Score: {total_risk_score}/100 [{risk_tier}]. Incident matches: {len(incidents)}, ADR policies: {len(adrs)}, Tier-0 intersection: {has_tier0}.",
            "data": {
                "score": total_risk_score,
                "tier": risk_tier,
                "breakdown": score_breakdown,
                "has_tier0": has_tier0,
                "has_p1_incident": has_p1
            }
        })

        return {
            "risk_score": total_risk_score,
            "risk_tier": risk_tier,
            "score_breakdown": score_breakdown,
            "incidents": incidents,
            "adrs": adrs,
            "metrics": metrics,
            "explainable_paths": explainable_paths,
            "has_tier0": has_tier0,
            "has_p1": has_p1,
            "trace_logs": trace_logs,
            "duration_ms": round((time.time() - start_t) * 1000, 2)
        }


class ActionAgent:
    """
    Action Agent:
    Acts directly upon graph evidence: selects tests, runs targeted tests,
    notifies owners, enforces safe approval gates, and commits persistent cross-session memory to FalkorDB.
    """
    def __init__(self, mcp):
        self.mcp = mcp
        self.role = "Action Agent"

    def execute_actions(self, pr_data: Dict[str, Any], investigation: Dict[str, Any], risk_analysis: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        trace_logs = []
        start_t = time.time()
        
        blast = investigation["blast_result"]
        blast_node_ids = [n["id"] for n in blast.get("nodes", [])]
        pr_id = pr_data.get("pr_id", "PR-UNKNOWN")

        # Step 1: Smart Test Selection based on FalkorDB coverage edges
        trace_logs.append({
            "agent": self.role,
            "phase": "MCP_TOOL_CALL",
            "message": "Invoking MCP tool 'select_impacted_tests' to isolate tests topologically mapped to blast radius...",
            "tool": "select_impacted_tests",
            "arguments": {"blast_node_ids": blast_node_ids}
        })
        test_selection = self.mcp.invoke_tool("select_impacted_tests", {"blast_node_ids": blast_node_ids})
        selected_tests = test_selection.get("selected_tests", [])
        test_files_to_run = list(set(t["test_node"]["file"] for t in selected_tests if t.get("test_node", {}).get("file")))

        trace_logs.append({
            "agent": self.role,
            "phase": "TEST_SELECTION_COMPLETE",
            "message": f"Graph-guided test selection: Selected {len(selected_tests)} out of {test_selection.get('total_suite_count')} tests ({test_selection.get('ci_reduction_percentage')}% CI pipeline savings).",
            "data": test_selection
        })

        # Step 2: Run targeted tests
        trace_logs.append({
            "agent": self.role,
            "phase": "MCP_TOOL_CALL",
            "message": f"Invoking MCP tool 'run_targeted_tests' on {len(test_files_to_run)} targeted test suites...",
            "tool": "run_targeted_tests",
            "arguments": {"test_files": test_files_to_run}
        })
        run_results = self.mcp.invoke_tool("run_targeted_tests", {"test_files": test_files_to_run})

        # Step 3: Find Stakeholders and Notification Routing
        trace_logs.append({
            "agent": self.role,
            "phase": "MCP_TOOL_CALL",
            "message": "Invoking MCP tool 'find_stakeholders' via FalkorDB ownership paths...",
            "tool": "find_stakeholders",
            "arguments": {"blast_node_ids": blast_node_ids}
        })
        stakeholders = self.mcp.invoke_tool("find_stakeholders", {"blast_node_ids": blast_node_ids})

        # Step 4: Evaluate Safe Approval Gate
        trace_logs.append({
            "agent": self.role,
            "phase": "MCP_TOOL_CALL",
            "message": "Invoking MCP tool 'evaluate_safe_approval_gate' to enforce production deployment policies...",
            "tool": "evaluate_safe_approval_gate",
            "arguments": {
                "risk_score": risk_analysis["risk_score"],
                "has_tier0_workflow": risk_analysis["has_tier0"],
                "has_p1_incident": risk_analysis["has_p1"],
                "has_adr_violation": len(risk_analysis.get("adrs", [])) > 0
            }
        })
        gate_decision = self.mcp.invoke_tool("evaluate_safe_approval_gate", {
            "risk_score": risk_analysis["risk_score"],
            "has_tier0_workflow": risk_analysis["has_tier0"],
            "has_p1_incident": risk_analysis["has_p1"],
            "has_adr_violation": len(risk_analysis.get("adrs", [])) > 0
        })

        # Step 5: Record Persistent Agent Memory into FalkorDB
        memory_summary = (
            f"Review for {pr_id} scored {risk_analysis['risk_score']}/100 ({risk_analysis['risk_tier']}). "
            f"Impacted {len(investigation['services'])} services, {len(investigation['workflows'])} workflows. "
            f"Gate policy: {gate_decision['gate_status']}. Tests executed: {run_results.get('executed_count', 0)}, "
            f"Pass status: {run_results.get('overall_pass')}."
        )
        trace_logs.append({
            "agent": self.role,
            "phase": "MCP_TOOL_CALL",
            "message": "Writing agent review memory and decision back to FalkorDB for persistent cross-session recall...",
            "tool": "record_agent_memory",
            "arguments": {"pr_id": pr_id, "summary": memory_summary, "risk_score": risk_analysis["risk_score"]}
        })
        memory_record = self.mcp.invoke_tool("record_agent_memory", {
            "session_id": session_id,
            "pr_id": pr_id,
            "agent_role": self.role,
            "summary": memory_summary,
            "risk_score": risk_analysis["risk_score"],
            "payload": {
                "affected_nodes": blast_node_ids,
                "risk_tier": risk_analysis["risk_tier"],
                "gate_status": gate_decision["gate_status"],
                "tests_passed": run_results.get("overall_pass"),
                "teams_notified": [t.get("name") for t in stakeholders.get("teams", [])]
            }
        })

        return {
            "test_selection": test_selection,
            "test_run_results": run_results,
            "stakeholders": stakeholders,
            "gate_decision": gate_decision,
            "persisted_memory": memory_record,
            "trace_logs": trace_logs,
            "duration_ms": round((time.time() - start_t) * 1000, 2)
        }


class RippleGuardCoordinator:
    """
    Main Multi-Agent Orchestrator:
    Coordinates Investigator, Risk Analyst, and Action Agents in a clean sequential loop,
    collating unified agent traces, graph state, and actionable impact intelligence.
    """
    def __init__(self):
        self.mcp = get_mcp_registry()
        self.investigator = InvestigatorAgent(self.mcp)
        self.risk_analyst = RiskAnalystAgent(self.mcp)
        self.action_agent = ActionAgent(self.mcp)

    def process_change_request(self, pr_data: Dict[str, Any]) -> Dict[str, Any]:
        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        start_time = time.time()

        # Phase 1: Investigator Agent
        investigation = self.investigator.investigate(pr_data, session_id)

        # Phase 2: Risk Analyst Agent
        risk_analysis = self.risk_analyst.analyze_risk(pr_data, investigation, session_id)

        # Phase 3: Action Agent
        action_results = self.action_agent.execute_actions(pr_data, investigation, risk_analysis, session_id)

        total_duration = round((time.time() - start_time) * 1000, 2)

        # Collate unified trace logs
        unified_traces = (
            investigation["trace_logs"] +
            risk_analysis["trace_logs"] +
            action_results["trace_logs"]
        )

        return {
            "session_id": session_id,
            "pr_data": pr_data,
            "investigation": {
                "services": investigation["services"],
                "apis": investigation["apis"],
                "tables": investigation["tables"],
                "columns": investigation["columns"],
                "workflows": investigation["workflows"],
                "total_nodes": investigation["blast_result"]["total_impacted_nodes"],
                "total_edges": investigation["blast_result"]["total_impacted_edges"],
                "blast_nodes": investigation["blast_result"]["nodes"],
                "blast_edges": investigation["blast_result"]["edges"]
            },
            "risk_analysis": {
                "score": risk_analysis["risk_score"],
                "tier": risk_analysis["risk_tier"],
                "breakdown": risk_analysis["score_breakdown"],
                "incidents": risk_analysis["incidents"],
                "adrs": risk_analysis["adrs"],
                "metrics": risk_analysis["metrics"],
                "explainable_paths": risk_analysis["explainable_paths"]
            },
            "action_results": {
                "test_selection": action_results["test_selection"],
                "test_run_results": action_results["test_run_results"],
                "stakeholders": action_results["stakeholders"],
                "gate_decision": action_results["gate_decision"],
                "persisted_memory": action_results["persisted_memory"]
            },
            "agent_traces": unified_traces,
            "execution_duration_ms": total_duration
        }

coordinator = RippleGuardCoordinator()

def get_coordinator() -> RippleGuardCoordinator:
    return coordinator
