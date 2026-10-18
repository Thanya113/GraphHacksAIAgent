import pytest

def test_payments_ledger_schema_contract():
    required_columns = {"transaction_id", "order_id", "amount_cents", "auth_token_hash", "status", "timestamp"}
    current_columns = {"transaction_id", "order_id", "amount_cents", "auth_token_hash", "status", "timestamp"}
    missing = required_columns - current_columns
    assert len(missing) == 0, f"Schema regression detected! Missing columns: {missing}"
