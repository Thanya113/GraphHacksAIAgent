"""
RippleGuard FastAPI Backend Server.
Exposes REST endpoints for the interactive dashboard, multi-agent coordination,
FalkorDB Cypher execution, safe gate approvals, and cross-session memory inspection.
"""
import os
import time
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from backend.falkor_engine import get_engine
from backend.mcp_tools import get_mcp_registry
from backend.agents import get_coordinator

app = FastAPI(
    title="RippleGuard API",
    description="Multi-Agent Change-Impact Intelligence System powered by FalkorDB",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = get_engine()
mcp = get_mcp_registry()
coordinator = get_coordinator()

# Pydantic models
class CypherQueryRequest(BaseModel):
    cypher: str
    params: Optional[Dict[str, Any]] = None

class ChangeRequestPayload(BaseModel):
    pr_id: str
    title: str
    description: Optional[str] = ""
    author: Optional[str] = "developer"
    changed_symbols: List[str]
    diff: Optional[str] = ""

class GateDecisionPayload(BaseModel):
    pr_id: str
    session_id: str
    decision: str  # "APPROVED" or "REJECTED"
    approver: str
    notes: Optional[str] = ""

# Pre-configured realistic PR Scenarios
PRESET_SCENARIOS = [
    {
        "id": "scenario_pr104",
        "pr_id": "PR-104",
        "title": "Refactor PaymentGateway token validation to strict JWT",
        "description": "Upgrades payment authorization token validation from legacy bearer strings to signed JWT tokens with 15-minute rotation.",
        "author": "Sarah Chen (Staff Engineer)",
        "service": "PaymentService",
        "changed_symbols": ["sym:PaymentGateway.verify_jwt_token"],
        "expected_risk": "CRITICAL (100/100)",
        "expected_gate": "BLOCKED_REQUIRES_DUAL_LEAD_APPROVAL",
        "diff": """@@ -15,7 +15,7 @@ class PaymentGateway:
-    def verify_jwt_token(self, token: str) -> dict:
-        if not token or not token.startswith("Bearer "):
+    def verify_jwt_token(self, token: str) -> dict:
+        # Strict signature check without legacy header fallback
+        if len(token.split(" ")[1]) < 10:
+            raise ValueError("Token signature verification failed")"""
    },
    {
        "id": "scenario_pr105",
        "pr_id": "PR-105",
        "title": "Reduce Inventory distributed lock timeout to 2000ms",
        "description": "Adjusts acquisition lock timeout in warehouse allocation to minimize redis thread contention.",
        "author": "Priya Patel (Senior Engineer)",
        "service": "InventoryService",
        "changed_symbols": ["sym:InventoryLocker.acquire_lock"],
        "expected_risk": "HIGH (68/100)",
        "expected_gate": "HOLD_REQUIRES_STAFF_APPROVAL",
        "diff": """@@ -13,7 +13,7 @@ class InventoryLocker:
-    def acquire_lock(self, sku: str, quantity: int, timeout_ms: int = 5000):
+    def acquire_lock(self, sku: str, quantity: int, timeout_ms: int = 2000):"""
    },
    {
        "id": "scenario_pr106",
        "pr_id": "PR-106",
        "title": "Add order receipt email delivery template",
        "description": "Updates customer notification receipt payload formatting with delivery timestamps.",
        "author": "Alex Rivera (Platform Security)",
        "service": "NotificationService",
        "changed_symbols": ["sym:NotificationClient.send_receipt"],
        "expected_risk": "LOW (18/100)",
        "expected_gate": "AUTO_APPROVED",
        "diff": """@@ -11,4 +11,6 @@ class NotificationClient:
+        msg["delivered"] = True
+        msg["sent_at"] = time.time()"""
    },
    {
        "id": "scenario_pr107",
        "pr_id": "PR-107",
        "title": "Drop deprecated orders.archived_flag column from schema",
        "description": "Removes legacy archived_flag column from orders table in postgres_primary database.",
        "author": "Marcus Vance (Principal Architect)",
        "service": "OrderService",
        "changed_symbols": ["col:orders.archived_flag", "sym:OrderWorkflow.process_payment"],
        "expected_risk": "HIGH (72/100)",
        "expected_gate": "HOLD_REQUIRES_STAFF_APPROVAL",
        "diff": """@@ -1,3 +1,2 @@
 ALTER TABLE orders
-  DROP COLUMN archived_flag;"""
    }
]

@app.get("/api/status")
def get_system_status():
    """Returns FalkorDB connection status and graph topology overview."""
    return engine.get_status()

@app.get("/api/graph")
def get_full_graph():
    """
    Returns the complete FalkorDB graph nodes and edges
    formatted for visualization in Cytoscape.js.
    """
    nodes = []
    for nid, data in engine.nodes_data.items():
        nodes.append({
            "data": {
                "id": nid,
                "label": data.get("name", nid),
                "type": data.get("label", "Unknown"),
                "tier": data.get("tier", ""),
                "kind": data.get("kind", ""),
                "file": data.get("file", ""),
                "severity": data.get("severity", ""),
                "properties": data
            }
        })

    edges = []
    for idx, e in enumerate(engine.edges_data):
        edges.append({
            "data": {
                "id": f"edge_{idx}_{e['source']}_{e['target']}",
                "source": e["source"],
                "target": e["target"],
                "type": e["type"],
                "label": e["type"]
            }
        })

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(edges)
        }
    }

@app.get("/api/scenarios")
def get_preset_scenarios():
    """Returns preset realistic PR scenarios for immediate one-click testing."""
    return PRESET_SCENARIOS

@app.post("/api/query/cypher")
def run_cypher_query(req: CypherQueryRequest):
    """Executes an openCypher query directly against FalkorDB."""
    try:
        res = engine.execute_cypher(req.cypher, req.params)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/analyze")
def analyze_change_request(payload: ChangeRequestPayload):
    """
    Triggers full multi-agent change impact analysis pipeline:
    Investigator Agent -> Risk Analyst Agent -> Action Agent.
    """
    try:
        result = coordinator.process_change_request(payload.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis pipeline error: {str(e)}")

@app.get("/api/memory")
def get_agent_memories(pr_id: Optional[str] = None, limit: int = 20):
    """Queries persistent cross-session AgentMemory nodes from FalkorDB."""
    memories = engine.query_cross_session_memories(pr_id=pr_id, limit=limit)
    return {"count": len(memories), "memories": memories}

@app.post("/api/gate/decision")
def record_gate_decision(payload: GateDecisionPayload):
    """
    Safe Approval Gate:
    Records an engineer's manual approval or rejection for a high-risk change,
    storing the decision back into FalkorDB as permanent audit memory.
    """
    mem_res = engine.record_agent_memory(
        session_id=payload.session_id,
        pr_id=payload.pr_id,
        agent_role="Human Review Gate",
        summary=f"Human Approver {payload.approver} submitted decision: {payload.decision}. Notes: {payload.notes or 'None'}",
        risk_score=0,
        payload={
            "decision": payload.decision,
            "approver": payload.approver,
            "notes": payload.notes,
            "timestamp": time.time()
        }
    )
    return {
        "status": "DECISION_COMMITTED",
        "decision": payload.decision,
        "approver": payload.approver,
        "memory": mem_res
    }

# Mount static frontend files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/")
def serve_index():
    index_file = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "RippleGuard API active. Frontend index.html not yet created."}
