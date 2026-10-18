import pytest
from services.inventory_service.locker import InventoryLocker

def test_acquire_lock_success():
    locker = InventoryLocker()
    res = locker.acquire_lock(sku="SKU-PHONE-X", quantity=5, timeout_ms=3000)
    assert res["success"] is True
    assert res["reserved_quantity"] == 5

def test_acquire_lock_invalid_qty():
    locker = InventoryLocker()
    with pytest.raises(ValueError):
        locker.acquire_lock(sku="SKU-PHONE-X", quantity=0)
