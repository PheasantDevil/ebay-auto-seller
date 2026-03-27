from sourcing_scan.logic import VariantInventoryInput, compute_on_hand_qty


def test_compute_on_hand_qty_applies_safety_stock():
    assert (
        compute_on_hand_qty(
            VariantInventoryInput(variant_id="v1", safety_stock_threshold=2, supplier_stock_qty=10)
        )
        == 8
    )


def test_compute_on_hand_qty_never_negative():
    assert (
        compute_on_hand_qty(
            VariantInventoryInput(variant_id="v1", safety_stock_threshold=5, supplier_stock_qty=3)
        )
        == 0
    )
