"""
RippleGuard MCP Tool Registry & Schema.
Exposes FalkorDB graph queries and graph algorithms as formal Model Context Protocol (MCP) tools.
"""
import os
import subprocess
import time
import json
import logging
from typing import Dict, List, Any, Optional
from backend.falkor_engine import get_engine

logger = logging.getLogger("rippleguard.mcp")


class MCPToolRegistry:
    """
    Standard MCP Tool Server and Registry.
    Provides typed tool declarations and handlers for the multi-agent system.
    """
    def __init__(self):
        self.engine = get_engine()

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Returns MCP-compliant tool metadata declarations."""
        return [
            {
                "name": "falkordb_graph_query",
                "description": "Execute openCypher queries directly against FalkorDB to inspect nodes, relationships, and graph state.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cypher": {"type": "string", "description": "The openCypher query string to execute."},
                        "params": {"type": "object", "description": "Optional parameterized query bindings."}
                    },
                    "required": ["cypher"]
                }
            },
            {
                "name": "trace_blast_radius",
                "description": "Discover all downstream and upstream connected entities (symbols, APIs, tables, workflows, incidents) reachable within N hops from modified symbols.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "seed_node_ids": {"type": "array", "items": {"type": "string"}, "description": "List of node IDs changed in PR (e.g. ['sym:PaymentGateway.verify_jwt_token'])."},
                        "max_depth": {"type": "integer", "description": "Maximum hops to traverse (default: 4)."}
                    },
                    "required": ["seed_node_ids"]
                }
            },
            {
                "name": "get_explainable_paths",
                "description": "Calculate shortest and all paths between a changed symbol and a high-risk target (e.g. critical workflow or past incident) to provide evidence-backed explanation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source_id": {"type": "string", "description": "Starting node ID (e.g., changed symbol)."},
                        "target_id": {"type": "string", "description": "Destination node ID (e.g., critical workflow or incident)."}
                    },
                    "required": ["source_id", "target_id"]
                }
            },
            {
                "name": "calculate_graph_metrics",
                "description": "Calculate graph algorithm metrics (degree centrality, betweenness centrality, in/out degree) across the blast radius using FalkorDB topology.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "node_ids": {"type": "array", "items": {"type": "string"}, "description": "List of node IDs to analyze."}
                    },
                    "required": ["node_ids"]
                }
            },
            {
                "name": "audit_incidents_and_adrs",
                "description": "Cross-reference the blast radius against historical P1/P2 incidents and Architectural Decision Records (ADRs) stored in FalkorDB.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "blast_node_ids": {"type": "array", "items": {"type": "string"}, "description": "Node IDs discovered in blast radius."}
                    },
                    "required": ["blast_node_ids"]
                }
            },
            {
                "name": "select_impacted_tests",
                "description": "Use FalkorDB test coverage relationships (COVERS_SYMBOL, COVERS_TABLE, VERIFIES_WORKFLOW) to select only the exact tests impacted by the change.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "blast_node_ids": {"type": "array", "items": {"type": "string"}, "description": "Node IDs in the blast radius."}
                    },
                    "required": ["blast_node_ids"]
                }
            },
            {
                "name": "find_stakeholders",
                "description": "Traverse FalkorDB ownership edges (PART_OF_SERVICE -> OWNED_BY -> HAS_LEAD) to identify required reviewers, leads, and on-call teams.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "blast_node_ids": {"type": "array", "items": {"type": "string"}, "description": "Node IDs in the blast radius."}
                    },
                    "required": ["blast_node_ids"]
                }
            },
            {
                "name": "record_agent_memory",
                "description": "Persist agent investigation findings, risk assessments, and decisions back into FalkorDB as AgentMemory nodes for cross-session intelligence.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string", "description": "Unique session identifier."},
                        "pr_id": {"type": "string", "description": "Pull Request ID (e.g., 'PR-104')."},
                        "agent_role": {"type": "string", "description": "Name of agent storing memory."},
                        "summary": {"type": "string", "description": "Concise summary of findings and rationale."},
                        "risk_score": {"type": "integer", "description": "Assigned risk score (0-100)."},
                        "payload": {"type": "object", "description": "Arbitrary structured evidence to persist."}
                    },
                    "required": ["session_id", "pr_id", "agent_role", "summary", "risk_score", "payload"]
                }
            },
            {
                "name": "query_cross_session_memory",
                "description": "Retrieve past agent analysis, approvals, and lessons learned from FalkorDB graph memory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pr_id": {"type": "string", "description": "Optional PR ID filter."},
                        "limit": {"type": "integer", "description": "Maximum memory records to return."}
                    }
                }
            },
            {
                "name": "run_targeted_tests",
                "description": "Execute the subset of tests identified by smart test selection and return pass/fail and latency results.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "test_files": {"type": "array", "items": {"type": "string"}, "description": "List of test file paths to execute."}
                    },
                    "required": ["test_files"]
                }
            },
            {
                "name": "evaluate_safe_approval_gate",
                "description": "Enforce automated safety policy gates based on graph evidence (risk score, Tier-0 workflows, incident links, and ADR compliance).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "risk_score": {"type": "integer", "description": "Calculated risk score."},
                        "has_tier0_workflow": {"type": "boolean", "description": "True if blast radius intersects Tier-0 workflow."},
                        "has_past_p1_incident": {"type": "boolean", "description": "True if component caused prior P1 incident."},
                        "has_adr_violation": {"type": "boolean", "description": "True if change violates an active ADR."}
                    },
                    "required": ["risk_score", "has_tier0_workflow"]
                }
            }
        ]

    def invoke_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches an MCP tool call and returns structured output."""
        start_t = time.time()
        logger.info(f"MCP Tool Invoke: {tool_name} with args {list(arguments.keys())}")

        if tool_name == "falkordb_graph_query":
            res = self.engine.execute_cypher(arguments["cypher"], arguments.get("params"))
            return res

        elif tool_name == "trace_blast_radius":
            res = self.engine.trace_blast_radius(
                arguments["seed_node_ids"],
                arguments.get("max_depth", 4)
            )
            return res

        elif tool_name == "get_explainable_paths":
            paths = self.engine.find_explainable_paths(
                arguments["source_id"],
                arguments["target_id"]
            )
            return {"source_id": arguments["source_id"], "target_id": arguments["target_id"], "paths": paths}

        elif tool_name == "calculate_graph_metrics":
            metrics = self.engine.calculate_centrality_metrics(arguments.get("node_ids"))
            return {"metrics": metrics}

        elif tool_name == "audit_incidents_and_adrs":
            blast_ids = set(arguments.get("blast_node_ids", []))
            incidents_found = []
            adrs_found = []

            # Find incidents linked to any node in blast radius
            for nid, node in self.engine.nodes_data.items():
                if node.get("label") == "Incident":
                    # Check if incident is linked to any blast node
                    neighbors = set(self.engine.nx_graph.neighbors(nid)) | set(self.engine.nx_graph.predecessors(nid))
                    inter = neighbors.intersection(blast_ids)
                    if inter or nid in blast_ids:
                        incidents_found.append({
                            "incident": node,
                            "linked_blast_nodes": [self.engine.nodes_data.get(x, {}).get("name", x) for x in inter]
                        })

                if node.get("label") == "ADR":
                    neighbors = set(self.engine.nx_graph.neighbors(nid)) | set(self.engine.nx_graph.predecessors(nid))
                    inter = neighbors.intersection(blast_ids)
                    if inter or nid in blast_ids:
                        adrs_found.append({
                            "adr": node,
                            "governed_blast_nodes": [self.engine.nodes_data.get(x, {}).get("name", x) for x in inter]
                        })

            return {
                "total_incidents": len(incidents_found),
                "incidents": incidents_found,
                "total_adrs": len(adrs_found),
                "adrs": adrs_found
            }

        elif tool_name == "select_impacted_tests":
            blast_ids = set(arguments.get("blast_node_ids", []))
            selected_tests = []
            all_tests = []

            for nid, node in self.engine.nodes_data.items():
                if node.get("label") == "TestCase":
                    all_tests.append(node)
                    # Check coverage edges: TestCase -> Symbol/Table/Workflow
                    coverage_targets = set(self.engine.nx_graph.neighbors(nid))
                    inter = coverage_targets.intersection(blast_ids)
                    if inter:
                        selected_tests.append({
                            "test_node": node,
                            "target_covered": [self.engine.nodes_data.get(x, {}).get("name", x) for x in inter]
                        })

            total_all = len(all_tests)
            total_selected = len(selected_tests)
            reduction_pct = round(((total_all - total_selected) / total_all) * 100, 1) if total_all else 0.0

            return {
                "total_suite_count": total_all,
                "selected_test_count": total_selected,
                "ci_reduction_percentage": reduction_pct,
                "selected_tests": selected_tests
            }

        elif tool_name == "find_stakeholders":
            blast_ids = set(arguments.get("blast_node_ids", []))
            teams = {}
            engineers = {}

            for nid in blast_ids:
                node = self.engine.nodes_data.get(nid, {})
                # Check neighbors for Team or Engineer
                neighbors = set(self.engine.nx_graph.neighbors(nid)) | set(self.engine.nx_graph.predecessors(nid))
                for nbr in neighbors:
                    nbr_node = self.engine.nodes_data.get(nbr, {})
                    if nbr_node.get("label") == "Team":
                        teams[nbr] = nbr_node
                    elif nbr_node.get("label") == "Engineer":
                        engineers[nbr] = nbr_node

            return {
                "teams": list(teams.values()),
                "engineers": list(engineers.values()),
                "slack_channels": list(set(t.get("slack") for t in teams.values() if t.get("slack"))),
                "pagerduty_services": list(set(t.get("pagerduty") for t in teams.values() if t.get("pagerduty")))
            }

        elif tool_name == "record_agent_memory":
            res = self.engine.record_agent_memory(
                session_id=arguments["session_id"],
                pr_id=arguments["pr_id"],
                agent_role=arguments["agent_role"],
                summary=arguments["summary"],
                risk_score=arguments["risk_score"],
                payload=arguments["payload"]
            )
            return res

        elif tool_name == "query_cross_session_memory":
            res = self.engine.query_cross_session_memories(
                pr_id=arguments.get("pr_id"),
                limit=arguments.get("limit", 10)
            )
            return {"memories": res}

        elif tool_name == "run_targeted_tests":
            test_files = arguments.get("test_files", [])
            test_results = []
            overall_pass = True

            for tf in test_files:
                # Run pytest for this test file
                t_start = time.time()
                try:
                    p = subprocess.run(
                        ["python", "-m", "pytest", tf, "-q"],
                        capture_output=True,
                        text=True,
                        timeout=15
                    )
                    passed = (p.returncode == 0)
                    if not passed:
                        overall_pass = False
                    test_results.append({
                        "file": tf,
                        "passed": passed,
                        "duration_ms": round((time.time() - t_start) * 1000, 2),
                        "output": p.stdout.strip() or p.stderr.strip()
                    })
                except Exception as e:
                    overall_pass = False
                    test_results.append({
                        "file": tf,
                        "passed": False,
                        "error": str(e)
                    })

            return {
                "overall_pass": overall_pass,
                "executed_count": len(test_results),
                "results": test_results
            }

        elif tool_name == "evaluate_safe_approval_gate":
            risk_score = arguments.get("risk_score", 0)
            has_tier0 = arguments.get("has_tier0_workflow", False)
            has_p1 = arguments.get("has_p1_incident", False)
            has_adr = arguments.get("has_adr_violation", False)

            gate_status = "APPROVED"
            reasons = []

            if risk_score >= 75 or (has_tier0 and has_p1):
                gate_status = "BLOCKED_REQUIRES_DUAL_LEAD_APPROVAL"
                reasons.append("Critical risk score (>=75) with direct path to historical P1 outage and Tier-0 revenue flow.")
            elif risk_score >= 50 or has_tier0 or has_adr:
                gate_status = "HOLD_REQUIRES_STAFF_APPROVAL"
                reasons.append("High risk or Tier-0 workflow impacted. Senior sign-off required.")
            elif risk_score >= 25:
                gate_status = "CONDITIONALLY_APPROVED"
                reasons.append("Medium risk. Automated tests must pass prior to merge.")
            else:
                gate_status = "AUTO_APPROVED"
                reasons.append("Low blast radius and zero critical workflow intersection.")

            return {
                "gate_status": gate_status,
                "requires_human_approval": gate_status.startswith("BLOCKED") or gate_status.startswith("HOLD"),
                "reasons": reasons,
                "risk_score": risk_score
            }

        else:
            raise ValueError(f"Unknown MCP Tool: {tool_name}")

mcp_registry = MCPToolRegistry()

def get_mcp_registry() -> MCPToolRegistry:
    return mcp_registry
