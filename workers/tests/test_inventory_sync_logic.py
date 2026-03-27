from inventory_sync_ebay.logic import ListingInventoryInput, needs_update


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
