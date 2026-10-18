"""
Order Service - Checkout Orchestration & Workflow Engine.
Coordinates checkout between Inventory and Payment services.
Powers Tier-0 Workflow WF-01 (Instant Checkout).
"""
import time
from services.payment_service.gateway import PaymentGateway

class OrderWorkflow:
    def __init__(self, payment_gateway: PaymentGateway = None):
        self.gateway = payment_gateway or PaymentGateway()

    def process_payment(self, order_id: str, amount_cents: int, auth_token: str) -> dict:
        """
        Direct caller of PaymentGateway.authorize_charge.
        Modifies Table: orders (columns: id, user_id, total_cents, status)
        Exposes API: POST /v1/orders/checkout
        """
        result = self.gateway.authorize_charge(amount_cents=amount_cents, auth_token=auth_token, order_id=order_id)
        return {
            "order_id": order_id,
            "status": "PAID" if result.get("success") else "PAYMENT_FAILED",
            "transaction_id": result.get("record", {}).get("transaction_id")
        }

class OrderController:
    def __init__(self):
        self.workflow = OrderWorkflow()

    def checkout_cart(self, user_id: str, cart_items: list, auth_token: str) -> dict:
        """
        Main entry point for checkout.
        """
        total_cents = sum(item.get("price_cents", 0) * item.get("qty", 1) for item in cart_items)
        order_id = f"ord_{int(time.time()*1000)}"
        return self.workflow.process_payment(order_id, total_cents, auth_token)
