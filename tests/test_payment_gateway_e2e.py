import pytest
from services.payment_service.gateway import PaymentGateway

def test_payment_gateway_authorize_charge_success():
    gw = PaymentGateway()
    token = "Bearer test_secret_token_12345"
    res = gw.authorize_charge(amount_cents=5000, auth_token=token, order_id="ord_test_01")
    assert res["success"] is True
    assert res["record"]["status"] == "CAPTURED"
    assert res["record"]["amount_cents"] == 5000

def test_payment_gateway_invalid_token():
    gw = PaymentGateway()
    with pytest.raises(ValueError):
        gw.authorize_charge(amount_cents=1000, auth_token="invalid_raw_token", order_id="ord_test_02")
