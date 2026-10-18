"""
Notification Service - Async transactional alerts and receipts.
Powers Workflow: WF-05 (Customer Notifications).
"""
import time

class NotificationClient:
    def __init__(self):
        self.sent_queue = []

    def send_receipt(self, user_email: str, order_id: str, amount_cents: int) -> dict:
        """
        Exposes API: POST /v1/notifications/email
        Modifies Table: audit_logs
        Powers Workflow: WF-05 (Customer Notifications)
        """
        msg_id = f"msg_{int(time.time()*1000)}"
        msg = {
            "message_id": msg_id,
            "to": user_email,
            "order_id": order_id,
            "amount_cents": amount_cents,
            "delivered": True,
            "sent_at": time.time()
        }
        self.sent_queue.append(msg)
        return msg
