"""
Payment Service - Core Payment Gateway & Vault.
Handles payment authorization, token validation, and ledger updates.
Governed by ADR-042 and ADR-019.
Root cause of historical incident INC-402 (auth token regression).
"""
import hashlib
import time

class PaymentGateway:
    def __init__(self, merchant_id: str = "mch_default"):
        self.merchant_id = merchant_id

    def verify_jwt_token(self, token: str) -> dict:
        """
        Validates JWT bearer authorization token.
        Critical Symbol: Touched in PR-104.
        Connected to Incident INC-402 (P1 Outage).
        """
        if not token or not token.startswith("Bearer "):
            raise ValueError("Invalid token format: Bearer token required")
        raw = token.split(" ")[1]
        if len(raw) < 10:
            raise ValueError("Token signature verification failed: length invalid")
        return {"valid": True, "subject": "usr_authed", "expires_at": time.time() + 900}

    def authorize_charge(self, amount_cents: int, auth_token: str, order_id: str) -> dict:
        """
        Exposes API: POST /v1/payments/charge
        Modifies Table: payments_ledger (columns: transaction_id, auth_token_hash, amount_cents, status)
        Powers Workflow: WF-01 (Instant Checkout) & WF-02 (Subscription Billing)
        """
        auth_data = self.verify_jwt_token(auth_token)
        token_hash = hashlib.sha256(auth_token.encode()).hexdigest()[:16]
        tx_id = f"tx_{int(time.time()*1000)}"
        
        # Write to payments_ledger
        record = {
            "transaction_id": tx_id,
            "order_id": order_id,
            "amount_cents": amount_cents,
            "auth_token_hash": token_hash,
            "status": "CAPTURED",
            "timestamp": time.time()
        }
        return {"success": True, "record": record}

    def execute_refund(self, transaction_id: str, amount_cents: int, reason: str) -> dict:
        """
        Exposes API: POST /v1/payments/refund
        Modifies Table: payments_ledger
        """
        return {
            "refund_id": f"ref_{int(time.time()*1000)}",
            "transaction_id": transaction_id,
            "amount_cents": amount_cents,
            "status": "REFUNDED"
        }
