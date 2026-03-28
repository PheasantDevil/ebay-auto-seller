from inventory_sync_ebay.logic import (
    ListingInventoryInput,
    needs_update,
    parse_inventory_policy,
)


def test_needs_update_true_when_qty_differs():
    assert (
        needs_update(
            ListingInventoryInput(
                ebay_listing_id="l1", ebay_item_id="i1", current_qty=1, desired_qty=0
            )
        )
        is True
    )


def test_needs_update_false_when_same():
    assert (
        needs_update(
            ListingInventoryInput(
                ebay_listing_id="l1", ebay_item_id="i1", current_qty=2, desired_qty=2
            )
        )
        is False
    )


def test_parse_inventory_policy_sku_and_offer():
    sku, oid = parse_inventory_policy(
        {"inventory_item_sku": " ABC ", "offer_id": "off-1"},
    )
    assert sku == "ABC"
    assert oid == "off-1"


def test_parse_inventory_policy_alternate_keys():
    sku, oid = parse_inventory_policy({"sku": "S1", "offerId": "O9"})
    assert sku == "S1"
    assert oid == "O9"


def test_parse_inventory_policy_empty():
    assert parse_inventory_policy(None) == (None, None)
    assert parse_inventory_policy({}) == (None, None)
