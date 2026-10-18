import pytest
from services.order_service.checkout import OrderController

def test_checkout_cart_integration():
    controller = OrderController()
    cart = [
        {"sku": "SKU-PROD-1", "price_cents": 2500, "qty": 2},
        {"sku": "SKU-PROD-2", "price_cents": 1000, "qty": 1}
    ]
    res = controller.checkout_cart(user_id="usr_99", cart_items=cart, auth_token="Bearer valid_secure_token_abc")
    assert res["status"] == "PAID"
    assert res["transaction_id"].startswith("tx_")
