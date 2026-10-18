import pytest
from services.notification_service.mailer import NotificationClient

def test_send_receipt_delivered():
    mailer = NotificationClient()
    res = mailer.send_receipt(user_email="alex@example.com", order_id="ord_99", amount_cents=1999)
    assert res["delivered"] is True
    assert res["to"] == "alex@example.com"
    assert len(mailer.sent_queue) == 1
