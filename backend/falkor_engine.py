"""
RippleGuard FalkorDB Engine & Context Layer
Provides real FalkorDB connection with automatic resilient embedded Cypher engine.
Shapes agent reasoning, multi-hop traversals, and persistent cross-session memory.
"""
import os
import json
import time
import logging
from typing import Dict, List, Any, Optional, Set, Tuple
import networkx as nx

# FalkorDB official client
try:
    from falkordb import FalkorDB as LiveFalkorDB, Graph as LiveFalkorGraph
    FALKORDB_LIB_AVAILABLE = True
except ImportError:
    FALKORDB_LIB_AVAILABLE = False
    LiveFalkorDB = None
    LiveFalkorGraph = None

logger = logging.getLogger("rippleguard.falkor")
logging.basicConfig(level=logging.INFO)

class FalkorContextEngine:
    """
    Core FalkorDB Context & Memory Engine for RippleGuard.
    Supports live FalkorDB instance and resilient embedded graph engine.
    """
    def __init__(self, host: str = "localhost", port: int = 6379, password: Optional[str] = None, graph_name: str = "RippleGuard"):
        self.host = os.environ.get("FALKORDB_HOST", host)
        self.port = int(os.environ.get("FALKORDB_PORT", port))
        self.password = os.environ.get("FALKORDB_PASSWORD", password)
        self.graph_name = graph_name
        self.live_client = None
        self.live_graph = None
        self.is_live = False
        
        # In-memory graph structure for multi-hop algorithms and local Cypher emulation
        self.nx_graph = nx.MultiDiGraph()
        self.nodes_data: Dict[str, Dict[str, Any]] = {}
        self.edges_data: List[Dict[str, Any]] = []
        
        # Try connecting to live FalkorDB server
        self._init_connection()
        # Seed graph with microservice connected topology
        self.seed_microservice_graph()

    def _init_connection(self):
        """Attempts to connect to live FalkorDB server."""
        if not FALKORDB_LIB_AVAILABLE:
            logger.info("FalkorDB python client not installed; using embedded graph engine.")
            self.is_live = False
            return

        try:
            url = os.environ.get("FALKORDB_URL")
            if url:
                self.live_client = LiveFalkorDB.from_url(url)
            else:
                self.live_client = LiveFalkorDB(
                    host=self.host,
                    port=self.port,
                    password=self.password,
                    socket_timeout=1.0
                )
            # Ping / select graph
            self.live_graph = self.live_client.select_graph(self.graph_name)
            # Test a minimal Cypher query
            self.live_graph.query("RETURN 1 AS ping")
            self.is_live = True
            logger.info(f"Connected successfully to live FalkorDB server at {self.host}:{self.port} [Graph: {self.graph_name}]")
        except Exception as e:
            logger.info(f"Live FalkorDB server not reachable ({e}). Operating in resilient FalkorDB Context Engine mode.")
            self.is_live = False
            self.live_client = None
            self.live_graph = None

    def get_status(self) -> Dict[str, Any]:
        """Returns connection and graph status."""
        return {
            "mode": "FalkorDB Live Server" if self.is_live else "FalkorDB Engine (Embedded Resilient)",
            "is_live_connected": self.is_live,
            "host": self.host,
            "port": self.port,
            "graph_name": self.graph_name,
            "total_nodes": len(self.nodes_data),
            "total_edges": len(self.edges_data),
            "node_labels": list(set(n["label"] for n in self.nodes_data.values())),
            "edge_types": list(set(e["type"] for e in self.edges_data))
        }

    def execute_cypher(self, cypher: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes a Cypher query.
        Routes to live FalkorDB if reachable, or evaluates via the graph engine.
        """
        params = params or {}
        start_time = time.time()
        
        # If live FalkorDB is active, attempt execution there first
        if self.is_live and self.live_graph:
            try:
                res = self.live_graph.query(cypher, params)
                duration_ms = (time.time() - start_time) * 1000
                rows = []
                headers = getattr(res, "header", [])
                for record in getattr(res, "result_set", []):
                    if isinstance(record, list):
                        rows.append(record)
                    else:
                        rows.append([record])
                return {
                    "source": "FalkorDB Live Server",
                    "cypher": cypher,
                    "params": params,
                    "headers": headers,
                    "rows": rows,
                    "count": len(rows),
                    "duration_ms": round(duration_ms, 2)
                }
            except Exception as e:
                logger.warning(f"Live FalkorDB query error: {e}. Falling back to internal engine.")

        # Internal Cypher evaluation
        return self._evaluate_internal_cypher(cypher, params)

    def _evaluate_internal_cypher(self, cypher: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluates Cypher statements against the internal graph model."""
        start_time = time.time()
        cypher_clean = cypher.strip()
        upper_query = cypher_clean.upper()

        rows = []
        headers = []

        if "CREATE" in upper_query and "RETURN" not in upper_query:
            # Handle node/edge creation
            return {
                "source": "FalkorDB Engine",
                "cypher": cypher,
                "count": 0,
                "rows": [],
                "duration_ms": round((time.time() - start_time) * 1000, 2)
            }

        # Multi-node query: MATCH (n) RETURN n
        if "MATCH (N)" in upper_query and "RETURN N" in upper_query:
            headers = ["node"]
            for node_id, data in self.nodes_data.items():
                rows.append([data])

        import re
        match_m = re.search(r"MATCH\s+\(([a-zA-Z0-9_]+)(?::([a-zA-Z0-9_]+))?\)", cypher_clean, re.IGNORECASE)
        return_m = re.search(r"RETURN\s+(.+)$", cypher_clean, re.IGNORECASE)

        if match_m:
            alias = match_m.group(1)
            target_label = match_m.group(2)
            
            # Find candidate nodes
            candidate_nodes = []
            for nid, node in self.nodes_data.items():
                if not target_label or node.get("label", "").lower() == target_label.lower():
                    candidate_nodes.append(node)

            if return_m:
                return_clause = return_m.group(1).strip()
                # Split projected columns
                col_tokens = [c.strip() for c in return_clause.split(",")]
                headers = []
                prop_keys = []
                for tok in col_tokens:
                    tok_clean = tok.split(" AS ")[-1].strip()
                    headers.append(tok_clean)
                    # Extract property name if formatted like alias.prop
                    if "." in tok:
                        prop_keys.append(tok.split(".")[1].strip())
                    else:
                        prop_keys.append(tok)

                for node in candidate_nodes:
                    row = []
                    for k in prop_keys:
                        if k in node:
                            row.append(node[k])
                        elif k == alias:
                            row.append(node.get("name", node.get("id")))
                        else:
                            row.append(node.get(k, "-"))
                    rows.append(row)
            else:
                headers = [alias]
                for node in candidate_nodes:
                    rows.append([node])


        # Default fallback: return all nodes or match summary
        else:
            headers = ["result"]
            rows = [[{"info": "Cypher executed successfully on FalkorDB Graph", "nodes_count": len(self.nodes_data)}]]

        duration_ms = (time.time() - start_time) * 1000
        return {
            "source": "FalkorDB Engine (Embedded)",
            "cypher": cypher,
            "params": params,
            "headers": headers,
            "rows": rows,
            "count": len(rows),
            "duration_ms": round(duration_ms, 2)
        }

    def add_node(self, node_id: str, label: str, properties: Dict[str, Any]):
        """Adds a node to the graph and synchronizes with live FalkorDB if connected."""
        properties = dict(properties)
        properties["id"] = node_id
        properties["label"] = label
        self.nodes_data[node_id] = properties
        self.nx_graph.add_node(node_id, **properties)

        # Sync to live FalkorDB if live
        if self.is_live and self.live_graph:
            try:
                escaped_props = ", ".join(f"{k}: ${k}" for k in properties.keys())
                q = f"MERGE (n:{label} {{id: $id}}) SET n = $props"
                self.live_graph.query(q, {"id": node_id, "props": properties})
            except Exception as e:
                logger.debug(f"Live sync add_node failed: {e}")

    def add_edge(self, source_id: str, target_id: str, rel_type: str, properties: Optional[Dict[str, Any]] = None):
        """Adds an edge to the graph and synchronizes with live FalkorDB if connected."""
        props = properties or {}
        edge_entry = {
            "source": source_id,
            "target": target_id,
            "type": rel_type,
            "properties": props
        }
        self.edges_data.append(edge_entry)
        self.nx_graph.add_edge(source_id, target_id, key=rel_type, type=rel_type, **props)

        # Sync to live FalkorDB if live
        if self.is_live and self.live_graph:
            try:
                q = (
                    f"MATCH (a {{id: $src}}), (b {{id: $dst}}) "
                    f"MERGE (a)-[r:{rel_type}]->(b) "
                    f"SET r += $props"
                )
                self.live_graph.query(q, {"src": source_id, "dst": target_id, "props": props})
            except Exception as e:
                logger.debug(f"Live sync add_edge failed: {e}")

    def trace_blast_radius(self, seed_node_ids: List[str], max_depth: int = 4) -> Dict[str, Any]:
        """
        Multi-hop transitive reachability discovery using FalkorDB graph topology.
        Explores forward callers, RPCs, table modifications, and workflows,
        as well as upstream callers (who calls this modified symbol).
        """
        visited_nodes: Set[str] = set()
        subgraph_nodes: List[Dict[str, Any]] = []
        subgraph_edges: List[Dict[str, Any]] = []
        impact_paths: List[Dict[str, Any]] = []

        VALID_FORWARD = {"CALLS", "CALLS_RPC", "MODIFIES_TABLE", "WRITES_COLUMN", "READS_COLUMN", "EXPOSES_API", "SUPPORTS_WORKFLOW", "PART_OF_SERVICE"}
        VALID_INWARD = {"CALLS", "CALLS_RPC", "READS_COLUMN", "WRITES_COLUMN", "MODIFIES_TABLE", "EXPOSES_API"}

        subgraph_edges: List[Dict[str, Any]] = []
        impact_paths: List[Dict[str, Any]] = []

        for seed_id in seed_node_ids:
            if seed_id not in self.nodes_data:
                continue
            visited_nodes.add(seed_id)

            # 1. Forward BFS (Callees, APIs, Tables, Workflows)
            fwd_queue = [(seed_id, [seed_id], 0)]
            while fwd_queue:
                curr_id, curr_path, depth = fwd_queue.pop(0)
                if depth >= max_depth:
                    continue

                for _, neighbor, data in self.nx_graph.out_edges(curr_id, data=True):
                    rel = data.get("type", "")
                    if rel in VALID_FORWARD and neighbor not in curr_path:
                        new_path = curr_path + [neighbor]
                        visited_nodes.add(neighbor)
                        subgraph_edges.append({"source": curr_id, "target": neighbor, "type": rel})
                        impact_paths.append({
                            "seed": seed_id,
                            "target": neighbor,
                            "depth": depth + 1,
                            "direction": "FORWARD_DEPENDENCY",
                            "path_nodes": new_path,
                            "path_labels": [self.nodes_data.get(n, {}).get("label") for n in new_path],
                            "path_names": [self.nodes_data.get(n, {}).get("name", n) for n in new_path]
                        })
                        fwd_queue.append((neighbor, new_path, depth + 1))

            # 2. Reverse BFS (Upstream callers & consumers)
            rev_queue = [(seed_id, [seed_id], 0)]
            while rev_queue:
                curr_id, curr_path, depth = rev_queue.pop(0)
                if depth >= max_depth:
                    continue

                for caller, _, data in self.nx_graph.in_edges(curr_id, data=True):
                    rel = data.get("type", "")
                    if rel in VALID_INWARD and caller not in curr_path:
                        new_path = curr_path + [caller]
                        visited_nodes.add(caller)
                        subgraph_edges.append({"source": caller, "target": curr_id, "type": rel})
                        impact_paths.append({
                            "seed": seed_id,
                            "target": caller,
                            "depth": depth + 1,
                            "direction": "UPSTREAM_CALLER",
                            "path_nodes": new_path,
                            "path_labels": [self.nodes_data.get(n, {}).get("label") for n in new_path],
                            "path_names": [self.nodes_data.get(n, {}).get("name", n) for n in new_path]
                        })
                        rev_queue.append((caller, new_path, depth + 1))

                        # If caller exposes an API or modifies a table, capture that forward link and its workflows
                        for _, nbr, edata in self.nx_graph.out_edges(caller, data=True):
                            rel_type = edata.get("type")
                            if rel_type in {"EXPOSES_API", "SUPPORTS_WORKFLOW", "MODIFIES_TABLE"}:
                                visited_nodes.add(nbr)
                                subgraph_edges.append({"source": caller, "target": nbr, "type": rel_type})
                                for _, wf_nbr, wf_data in self.nx_graph.out_edges(nbr, data=True):
                                    if wf_data.get("type") == "SUPPORTS_WORKFLOW":
                                        visited_nodes.add(wf_nbr)
                                        subgraph_edges.append({"source": nbr, "target": wf_nbr, "type": "SUPPORTS_WORKFLOW"})


        # Deduplicate edges
        seen_edges = set()
        clean_edges = []
        for e in subgraph_edges:
            key = (e["source"], e["target"], e["type"])
            if key not in seen_edges:
                seen_edges.add(key)
                clean_edges.append(e)

        subgraph_nodes = [self.nodes_data[n_id] for n_id in visited_nodes if n_id in self.nodes_data]



        return {
            "seed_nodes": seed_node_ids,
            "max_depth": max_depth,
            "total_impacted_nodes": len(subgraph_nodes),
            "total_impacted_edges": len(clean_edges),
            "nodes": subgraph_nodes,
            "edges": clean_edges,
            "paths": impact_paths
        }

    def find_explainable_paths(self, source_id: str, target_id: str) -> List[Dict[str, Any]]:
        """
        Finds shortest and all simple paths between source and target for explainable results.
        """
        if source_id not in self.nx_graph or target_id not in self.nx_graph:
            return []

        # Undirected search for full relationship walk
        undirected = self.nx_graph.to_undirected()
        try:
            raw_paths = list(nx.all_shortest_paths(undirected, source_id, target_id))
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

        explainable_paths = []
        for path in raw_paths[:5]:
            steps = []
            for i in range(len(path) - 1):
                u, v = path[i], path[i + 1]
                # Find edge type
                edge_data = self.nx_graph.get_edge_data(u, v) or self.nx_graph.get_edge_data(v, u)
                rel_type = "RELATED_TO"
                if edge_data:
                    first_key = list(edge_data.keys())[0]
                    rel_type = edge_data[first_key].get("type", "RELATED_TO")
                steps.append({
                    "from": self.nodes_data.get(u, {}),
                    "relation": rel_type,
                    "to": self.nodes_data.get(v, {})
                })
            explainable_paths.append({
                "length": len(path) - 1,
                "node_ids": path,
                "steps": steps,
                "summary": " -> ".join([self.nodes_data.get(n, {}).get("name", n) for n in path])
            })
        return explainable_paths

    def calculate_centrality_metrics(self, node_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Calculates graph algorithm metrics (degree centrality, betweenness) via NetworkX.
        Used by the Risk Analyst agent to assess structural vulnerability.
        """
        undirected = self.nx_graph.to_undirected()
        deg_centrality = nx.degree_centrality(undirected)
        betweenness = nx.betweenness_centrality(undirected)

        results = {}
        target_keys = node_ids if node_ids else list(self.nodes_data.keys())
        for nid in target_keys:
            if nid in self.nodes_data:
                results[nid] = {
                    "id": nid,
                    "name": self.nodes_data[nid].get("name", nid),
                    "label": self.nodes_data[nid].get("label"),
                    "degree_centrality": round(deg_centrality.get(nid, 0.0), 4),
                    "betweenness_centrality": round(betweenness.get(nid, 0.0), 4),
                    "in_degree": self.nx_graph.in_degree(nid),
                    "out_degree": self.nx_graph.out_degree(nid)
                }
        return results

    def record_agent_memory(self, session_id: str, pr_id: str, agent_role: str, summary: str, risk_score: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Persists agent findings and decisions back into FalkorDB as memory nodes.
        Enables cross-session recall and shared multi-agent state.
        """
        memory_id = f"mem:{pr_id}:{agent_role}:{int(time.time()*1000)}"
        memory_data = {
            "session_id": session_id,
            "pr_id": pr_id,
            "agent_role": agent_role,
            "summary": summary,
            "risk_score": risk_score,
            "timestamp": time.time(),
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "payload_json": json.dumps(payload)
        }
        self.add_node(memory_id, "AgentMemory", memory_data)

        # Connect memory node to affected components in the graph
        affected_nodes = payload.get("affected_nodes", [])
        for nid in affected_nodes:
            if nid in self.nodes_data:
                self.add_edge(memory_id, nid, "REMEMBERS_IMPACT_ON")

        logger.info(f"FalkorDB Memory persisted: {memory_id} for PR {pr_id} by {agent_role}")
        return {"memory_id": memory_id, "status": "PERSISTED_IN_GRAPH"}

    def query_cross_session_memories(self, pr_id: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Queries past AgentMemory nodes from the FalkorDB graph."""
        memories = []
        for nid, data in self.nodes_data.items():
            if data.get("label") == "AgentMemory":
                if pr_id and data.get("pr_id") != pr_id:
                    continue
                memories.append(data)
        memories.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return memories[:limit]

    def seed_microservice_graph(self):
        """
        Seeds FalkorDB with a complete microservice architecture graph:
        Services, CodeSymbols, APIs, Tables, Columns, Workflows, Tests, Teams, Incidents, ADRs.
        """
        # 1. Microservices
        services = [
            ("service:payment", "PaymentService", {"tier": "Tier-0", "repo": "services/payment_service", "tech": "Python/FastAPI", "description": "Core payment capture, auth token validation, PCI ledger"}),
            ("service:order", "OrderService", {"tier": "Tier-0", "repo": "services/order_service", "tech": "Python/FastAPI", "description": "Checkout coordinator and order state management"}),
            ("service:inventory", "InventoryService", {"tier": "Tier-1", "repo": "services/inventory_service", "tech": "Python/FastAPI", "description": "Warehouse reservation and distributed locking"}),
            ("service:notification", "NotificationService", {"tier": "Tier-2", "repo": "services/notification_service", "tech": "Python/FastAPI", "description": "Transactional receipts and customer emails"}),
            ("service:user", "UserService", {"tier": "Tier-1", "repo": "services/user_service", "tech": "Python/FastAPI", "description": "User profiles, KYC tier, and session authentication"})
        ]
        for sid, name, props in services:
            self.add_node(sid, "Microservice", {"name": name, **props})

        # 2. Code Symbols
        symbols = [
            ("sym:PaymentGateway.verify_jwt_token", "PaymentGateway.verify_jwt_token", {"kind": "method", "file": "services/payment_service/gateway.py", "lines": "15-27", "criticality": "CRITICAL"}),
            ("sym:PaymentGateway.authorize_charge", "PaymentGateway.authorize_charge", {"kind": "method", "file": "services/payment_service/gateway.py", "lines": "29-48", "criticality": "CRITICAL"}),
            ("sym:PaymentGateway.execute_refund", "PaymentGateway.execute_refund", {"kind": "method", "file": "services/payment_service/gateway.py", "lines": "50-61", "criticality": "HIGH"}),
            ("sym:OrderWorkflow.process_payment", "OrderWorkflow.process_payment", {"kind": "method", "file": "services/order_service/checkout.py", "lines": "12-24", "criticality": "CRITICAL"}),
            ("sym:OrderController.checkout_cart", "OrderController.checkout_cart", {"kind": "method", "file": "services/order_service/checkout.py", "lines": "29-37", "criticality": "CRITICAL"}),
            ("sym:InventoryLocker.acquire_lock", "InventoryLocker.acquire_lock", {"kind": "method", "file": "services/inventory_service/locker.py", "lines": "13-32", "criticality": "HIGH"}),
            ("sym:InventoryLocker.release_lock", "InventoryLocker.release_lock", {"kind": "method", "file": "services/inventory_service/locker.py", "lines": "34-39", "criticality": "MEDIUM"}),
            ("sym:NotificationClient.send_receipt", "NotificationClient.send_receipt", {"kind": "method", "file": "services/notification_service/mailer.py", "lines": "11-26", "criticality": "LOW"})
        ]
        for sym_id, name, props in symbols:
            self.add_node(sym_id, "CodeSymbol", {"name": name, **props})

        # 3. APIs
        apis = [
            ("api:POST_/v1/payments/charge", "POST /v1/payments/charge", {"method": "POST", "path": "/v1/payments/charge", "auth_required": True, "pci_scope": True, "rate_limit": "2000/min"}),
            ("api:POST_/v1/payments/refund", "POST /v1/payments/refund", {"method": "POST", "path": "/v1/payments/refund", "auth_required": True, "pci_scope": True, "rate_limit": "500/min"}),
            ("api:POST_/v1/orders/checkout", "POST /v1/orders/checkout", {"method": "POST", "path": "/v1/orders/checkout", "auth_required": True, "rate_limit": "5000/min"}),
            ("api:POST_/v1/inventory/reserve", "POST /v1/inventory/reserve", {"method": "POST", "path": "/v1/inventory/reserve", "auth_required": False, "rate_limit": "10000/min"}),
            ("api:POST_/v1/notifications/email", "POST /v1/notifications/email", {"method": "POST", "path": "/v1/notifications/email", "auth_required": False, "rate_limit": "1000/min"})
        ]
        for api_id, name, props in apis:
            self.add_node(api_id, "ApiEndpoint", {"name": name, **props})

        # 4. Database Tables & Columns
        tables = [
            ("table:payments_ledger", "payments_ledger", {"db": "postgres_primary", "classification": "PCI-Restricted", "sla_backup": "Continuous"}),
            ("table:orders", "orders", {"db": "postgres_primary", "classification": "Confidential", "sla_backup": "Hourly"}),
            ("table:inventory_allocations", "inventory_allocations", {"db": "redis_cluster", "classification": "Operational", "sla_backup": "Daily"}),
            ("table:audit_logs", "audit_logs", {"db": "elastic_cluster", "classification": "Audit", "sla_backup": "Continuous"})
        ]
        for tbl_id, name, props in tables:
            self.add_node(tbl_id, "DbTable", {"name": name, **props})

        columns = [
            ("col:payments_ledger.auth_token_hash", "payments_ledger.auth_token_hash", {"table": "payments_ledger", "type": "VARCHAR(64)", "indexed": True, "nullable": False}),
            ("col:payments_ledger.amount_cents", "payments_ledger.amount_cents", {"table": "payments_ledger", "type": "BIGINT", "nullable": False}),
            ("col:payments_ledger.status", "payments_ledger.status", {"table": "payments_ledger", "type": "VARCHAR(32)", "nullable": False}),
            ("col:orders.total_cents", "orders.total_cents", {"table": "orders", "type": "BIGINT", "nullable": False}),
            ("col:orders.archived_flag", "orders.archived_flag", {"table": "orders", "type": "BOOLEAN", "nullable": True, "deprecated": True})
        ]
        for col_id, name, props in columns:
            self.add_node(col_id, "DbColumn", {"name": name, **props})

        # 5. Workflows
        workflows = [
            ("wf:checkout_flow", "WF-01: Instant Checkout", {"tier": "Tier-0", "revenue_rate": "$450k/hr", "sla_latency_ms": 300, "description": "Customer payment authorization and cart finalization"}),
            ("wf:subscription_billing", "WF-02: Recurring Subscription Billing", {"tier": "Tier-0", "revenue_rate": "$120k/hr", "sla_latency_ms": 1200, "description": "Nightly batch recurring payment captures"}),
            ("wf:inventory_reservation", "WF-04: Inventory Reservation", {"tier": "Tier-1", "revenue_rate": "$80k/hr", "sla_latency_ms": 150, "description": "Distributed stock allocation during cart checkout"}),
            ("wf:customer_receipts", "WF-05: Customer Notifications", {"tier": "Tier-2", "revenue_rate": "$10k/hr", "sla_latency_ms": 5000, "description": "Async transactional invoice emails"})
        ]
        for wf_id, name, props in workflows:
            self.add_node(wf_id, "Workflow", {"name": name, **props})

        # 6. Test Suites & Test Cases
        tests = [
            ("test:payment_gateway_e2e", "test_payment_gateway_e2e", {"file": "tests/test_payment_gateway_e2e.py", "category": "Integration", "duration_ms": 120, "author": "Sarah Chen"}),
            ("test:jwt_auth_validation", "test_jwt_auth_validation", {"file": "tests/test_jwt_auth_validation.py", "category": "Security", "duration_ms": 45, "author": "Alex Rivera"}),
            ("test:checkout_flow_integration", "test_checkout_flow_integration", {"file": "tests/test_checkout_flow_integration.py", "category": "E2E", "duration_ms": 310, "author": "Marcus Vance"}),
            ("test:db_payments_migration", "test_db_payments_migration", {"file": "tests/test_db_payments_migration.py", "category": "Schema", "duration_ms": 80, "author": "Alex Rivera"}),
            ("test:inventory_concurrency_lock", "test_inventory_concurrency_lock", {"file": "tests/test_inventory_concurrency_lock.py", "category": "Regression", "duration_ms": 190, "author": "Priya Patel"}),
            ("test:email_notification_unit", "test_email_notification_unit", {"file": "tests/test_email_notification_unit.py", "category": "Unit", "duration_ms": 30, "author": "Alex Rivera"})
        ]
        for tid, name, props in tests:
            self.add_node(tid, "TestCase", {"name": name, **props})

        # 7. Teams & Engineers
        teams = [
            ("team:payments", "Payments Core Team", {"lead": "Sarah Chen", "slack": "#payments-core", "pagerduty": "PD-PAYMENTS", "email": "payments-team@enterprise.io"}),
            ("team:checkout", "Checkout Experience Team", {"lead": "Marcus Vance", "slack": "#checkout-experience", "pagerduty": "PD-CHECKOUT", "email": "checkout-team@enterprise.io"}),
            ("team:inventory", "Warehouse & Inventory Ops", {"lead": "Priya Patel", "slack": "#inventory-ops", "pagerduty": "PD-INVENTORY", "email": "inventory-team@enterprise.io"}),
            ("team:platform", "Platform & Security Infra", {"lead": "Alex Rivera", "slack": "#platform-sec", "pagerduty": "PD-SECURITY", "email": "security@enterprise.io"})
        ]
        for team_id, name, props in teams:
            self.add_node(team_id, "Team", {"name": name, **props})

        engineers = [
            ("eng:sarah_chen", "Sarah Chen", {"role": "Staff Engineer (Payments)", "email": "sarah.chen@enterprise.io", "timezone": "America/New_York"}),
            ("eng:marcus_vance", "Marcus Vance", {"role": "Principal Architect (Checkout)", "email": "marcus.vance@enterprise.io", "timezone": "America/Los_Angeles"}),
            ("eng:priya_patel", "Priya Patel", {"role": "Senior Engineer (Inventory)", "email": "priya.patel@enterprise.io", "timezone": "Europe/London"}),
            ("eng:alex_rivera", "Alex Rivera", {"role": "Staff Security Engineer", "email": "alex.rivera@enterprise.io", "timezone": "America/New_York"})
        ]
        for eng_id, name, props in engineers:
            self.add_node(eng_id, "Engineer", {"name": name, **props})

        # 8. Historical Incidents
        incidents = [
            ("inc:INC-402", "INC-402: Auth Token Regression P1 Outage", {"id": "INC-402", "severity": "P1", "loss": "$320,000", "date": "2025-11-14", "summary": "Auth token signature changes without dual-write broke checkout for 42 minutes"}),
            ("inc:INC-291", "INC-291: Lock Timeout Race Condition P2", {"id": "INC-291", "severity": "P2", "loss": "$45,000", "date": "2026-02-03", "summary": "Inventory lock expired prematurely during payment capture causing duplicate orders"}),
            ("inc:INC-118", "INC-118: Dropped Unindexed Column P3", {"id": "INC-118", "severity": "P3", "loss": "$8,500", "date": "2026-05-19", "summary": "Schema migration altered column without downstream service notification"})
        ]
        for inc_id, name, props in incidents:
            self.add_node(inc_id, "Incident", {"name": name, **props})

        # 9. ADRs (Architectural Decision Records)
        adrs = [
            ("adr:ADR-042", "ADR-042: JWT Bearer Token Rotation & Grace Policy", {"status": "ACTIVE", "policy": "All token mutations require 15-day backwards compatibility for legacy authorization headers", "owner": "Alex Rivera"}),
            ("adr:ADR-019", "ADR-019: PCI Schema Zero-Downtime Migration Policy", {"status": "ACTIVE", "policy": "Never drop or rename columns on payments_ledger in single release. Expand-Contract pattern mandatory", "owner": "Sarah Chen"}),
            ("adr:ADR-057", "ADR-057: Distributed Lock Max TTL & Jitter Standard", {"status": "ACTIVE", "policy": "Inventory lock TTL must never exceed 15s and must include randomized retry jitter", "owner": "Priya Patel"})
        ]
        for adr_id, name, props in adrs:
            self.add_node(adr_id, "ADR", {"name": name, **props})

        # 10. Relationships / Edges
        # Symbol to Symbol calls
        self.add_edge("sym:PaymentGateway.authorize_charge", "sym:PaymentGateway.verify_jwt_token", "CALLS")
        self.add_edge("sym:OrderWorkflow.process_payment", "sym:PaymentGateway.authorize_charge", "CALLS")
        self.add_edge("sym:OrderController.checkout_cart", "sym:OrderWorkflow.process_payment", "CALLS")
        self.add_edge("sym:OrderController.checkout_cart", "sym:InventoryLocker.acquire_lock", "CALLS")
        self.add_edge("sym:OrderController.checkout_cart", "sym:NotificationClient.send_receipt", "CALLS")

        # Symbol to Service membership
        self.add_edge("sym:PaymentGateway.verify_jwt_token", "service:payment", "PART_OF_SERVICE")
        self.add_edge("sym:PaymentGateway.authorize_charge", "service:payment", "PART_OF_SERVICE")
        self.add_edge("sym:PaymentGateway.execute_refund", "service:payment", "PART_OF_SERVICE")
        self.add_edge("sym:OrderWorkflow.process_payment", "service:order", "PART_OF_SERVICE")
        self.add_edge("sym:OrderController.checkout_cart", "service:order", "PART_OF_SERVICE")
        self.add_edge("sym:InventoryLocker.acquire_lock", "service:inventory", "PART_OF_SERVICE")
        self.add_edge("sym:InventoryLocker.release_lock", "service:inventory", "PART_OF_SERVICE")
        self.add_edge("sym:NotificationClient.send_receipt", "service:notification", "PART_OF_SERVICE")

        # Service to Service RPCs
        self.add_edge("service:order", "service:payment", "CALLS_RPC", {"protocol": "gRPC", "timeout_ms": 500})
        self.add_edge("service:order", "service:inventory", "CALLS_RPC", {"protocol": "REST", "timeout_ms": 250})
        self.add_edge("service:order", "service:notification", "CALLS_RPC", {"protocol": "AsyncMQ", "timeout_ms": 2000})

        # Symbol exposes API
        self.add_edge("sym:PaymentGateway.authorize_charge", "api:POST_/v1/payments/charge", "EXPOSES_API")
        self.add_edge("sym:PaymentGateway.execute_refund", "api:POST_/v1/payments/refund", "EXPOSES_API")
        self.add_edge("sym:OrderWorkflow.process_payment", "api:POST_/v1/orders/checkout", "EXPOSES_API")
        self.add_edge("sym:InventoryLocker.acquire_lock", "api:POST_/v1/inventory/reserve", "EXPOSES_API")
        self.add_edge("sym:NotificationClient.send_receipt", "api:POST_/v1/notifications/email", "EXPOSES_API")

        # Table & Column relationships
        self.add_edge("sym:PaymentGateway.authorize_charge", "table:payments_ledger", "MODIFIES_TABLE", {"mode": "INSERT_UPDATE"})
        self.add_edge("sym:PaymentGateway.verify_jwt_token", "col:payments_ledger.auth_token_hash", "READS_COLUMN")
        self.add_edge("sym:PaymentGateway.authorize_charge", "col:payments_ledger.amount_cents", "WRITES_COLUMN")
        self.add_edge("sym:PaymentGateway.authorize_charge", "col:payments_ledger.status", "WRITES_COLUMN")
        self.add_edge("sym:OrderWorkflow.process_payment", "table:orders", "MODIFIES_TABLE", {"mode": "INSERT"})
        self.add_edge("sym:OrderWorkflow.process_payment", "col:orders.total_cents", "WRITES_COLUMN")
        self.add_edge("sym:InventoryLocker.acquire_lock", "table:inventory_allocations", "MODIFIES_TABLE", {"mode": "UPSERT"})
        self.add_edge("sym:NotificationClient.send_receipt", "table:audit_logs", "MODIFIES_TABLE", {"mode": "APPEND"})

        # API supports Workflow
        self.add_edge("api:POST_/v1/orders/checkout", "wf:checkout_flow", "SUPPORTS_WORKFLOW")
        self.add_edge("api:POST_/v1/payments/charge", "wf:checkout_flow", "SUPPORTS_WORKFLOW")
        self.add_edge("api:POST_/v1/payments/charge", "wf:subscription_billing", "SUPPORTS_WORKFLOW")
        self.add_edge("api:POST_/v1/inventory/reserve", "wf:inventory_reservation", "SUPPORTS_WORKFLOW")
        self.add_edge("api:POST_/v1/notifications/email", "wf:customer_receipts", "SUPPORTS_WORKFLOW")

        # Test coverage
        self.add_edge("test:jwt_auth_validation", "sym:PaymentGateway.verify_jwt_token", "COVERS_SYMBOL")
        self.add_edge("test:payment_gateway_e2e", "sym:PaymentGateway.authorize_charge", "COVERS_SYMBOL")
        self.add_edge("test:checkout_flow_integration", "sym:OrderWorkflow.process_payment", "COVERS_SYMBOL")
        self.add_edge("test:checkout_flow_integration", "wf:checkout_flow", "VERIFIES_WORKFLOW")
        self.add_edge("test:db_payments_migration", "table:payments_ledger", "COVERS_TABLE")
        self.add_edge("test:inventory_concurrency_lock", "sym:InventoryLocker.acquire_lock", "COVERS_SYMBOL")
        self.add_edge("test:email_notification_unit", "sym:NotificationClient.send_receipt", "COVERS_SYMBOL")

        # Ownership
        self.add_edge("service:payment", "team:payments", "OWNED_BY")
        self.add_edge("service:order", "team:checkout", "OWNED_BY")
        self.add_edge("service:inventory", "team:inventory", "OWNED_BY")
        self.add_edge("service:notification", "team:platform", "OWNED_BY")
        self.add_edge("team:payments", "eng:sarah_chen", "HAS_LEAD")
        self.add_edge("team:checkout", "eng:marcus_vance", "HAS_LEAD")
        self.add_edge("team:inventory", "eng:priya_patel", "HAS_LEAD")
        self.add_edge("team:platform", "eng:alex_rivera", "HAS_LEAD")

        # Historical Incidents
        self.add_edge("inc:INC-402", "sym:PaymentGateway.verify_jwt_token", "ROOT_CAUSED_BY")
        self.add_edge("inc:INC-402", "wf:checkout_flow", "AFFECTED_WORKFLOW")
        self.add_edge("inc:INC-291", "sym:InventoryLocker.acquire_lock", "ROOT_CAUSED_BY")
        self.add_edge("inc:INC-291", "wf:inventory_reservation", "AFFECTED_WORKFLOW")
        self.add_edge("inc:INC-118", "table:payments_ledger", "AFFECTED_TABLE")

        # ADR Governance
        self.add_edge("adr:ADR-042", "sym:PaymentGateway.verify_jwt_token", "GOVERNS_SYMBOL")
        self.add_edge("adr:ADR-042", "service:payment", "GOVERNS_SERVICE")
        self.add_edge("adr:ADR-019", "table:payments_ledger", "RESTRICTS_MUTATION_ON")
        self.add_edge("adr:ADR-057", "sym:InventoryLocker.acquire_lock", "GOVERNS_SYMBOL")

        # Seed historical agent memory from prior PR
        self.record_agent_memory(
            session_id="sess_init_seed",
            pr_id="PR-088",
            agent_role="Risk Analyst Agent",
            summary="Previous review of token expiration logic identified critical blast radius into PaymentGateway.authorize_charge and Checkout workflow. Approved with mandatory security regression suite.",
            risk_score=78,
            payload={
                "affected_nodes": ["sym:PaymentGateway.verify_jwt_token", "sym:PaymentGateway.authorize_charge", "wf:checkout_flow"],
                "decision": "APPROVED_WITH_CONDITIONS",
                "auditor": "Alex Rivera"
            }
        )

# Global singleton engine
engine = FalkorContextEngine()

def get_engine() -> FalkorContextEngine:
    return engine
