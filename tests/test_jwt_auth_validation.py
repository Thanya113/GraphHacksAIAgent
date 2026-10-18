import pytest
from services.payment_service.gateway import PaymentGateway

def test_jwt_auth_validation_valid():
    gw = PaymentGateway()
    token = "Bearer eyJhbGciOiJIUzI1NiJ9_token_payload_valid"
    res = gw.verify_jwt_token(token)
    assert res["valid"] is True
    assert res["subject"] == "usr_authed"

def test_jwt_auth_validation_short_signature():
    gw = PaymentGateway()
    with pytest.raises(ValueError, match="signature verification failed"):
        gw.verify_jwt_token("Bearer short")
