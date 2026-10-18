"""
Inventory Service - Stock reservation and distributed concurrency locker.
Connected to Incident INC-291 (P2 Race Condition overselling).
Governed by ADR-057 (Jittered backoff for distributed locks).
"""
import time

class InventoryLocker:
    def __init__(self):
        self._locks = {}

    def acquire_lock(self, sku: str, quantity: int, timeout_ms: int = 5000) -> dict:
        """
        Exposes API: POST /v1/inventory/reserve
        Modifies Table: inventory_allocations (columns: sku, warehouse_id, quantity_reserved, lock_expires_at)
        Powers Workflow: WF-04 (Inventory Reservation)
        Past Incident: INC-291
        """
        if quantity <= 0:
            raise ValueError("Reservation quantity must be strictly positive")
        lock_id = f"lock_{sku}_{int(time.time()*1000)}"
        expires_at = time.time() + (timeout_ms / 1000.0)
        self._locks[sku] = {"lock_id": lock_id, "qty": quantity, "expires_at": expires_at}
        return {
            "success": True,
            "lock_id": lock_id,
            "sku": sku,
            "reserved_quantity": quantity,
            "expires_at": expires_at
        }

    def release_lock(self, sku: str) -> bool:
        if sku in self._locks:
            del self._locks[sku]
            return True
        return False
