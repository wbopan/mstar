from domains.customer_support.environment import CustomerSupportEnvironment
from domains.customer_support.schemas import CSEnvironmentData, Customer, Order, OrderItem, Product


def _make_env(*, item_status: str, order_status: str, shipping_status: str) -> CustomerSupportEnvironment:
    product = Product(
        product_id="PROD-1",
        name="Test Shirt",
        category="clothing",
        subcategory="shirt",
        price=59,
        warranty_months=0,
        return_window_days=30,
        restocking_fee_pct=0,
        weight_lbs=1.0,
        is_fragile=False,
        in_stock=True,
    )
    customer = Customer(
        customer_id="cust_001",
        name="Test User",
        email="test@example.com",
        membership_tier="standard",
        preferred_refund_method="original_payment",
    )
    order = Order(
        order_id="ORD-1",
        customer_id="cust_001",
        order_date="2026-06-01T10:00:00",
        status=order_status,
        shipping_status=shipping_status,
        shipping_method="standard",
        shipping_cost=8,
        tracking_number="TRK-1",
        delivery_date="2026-06-05T12:00:00" if item_status == "delivered" else None,
        delivery_promised_date="2026-06-05T18:00:00",
        payment_method="credit_card",
        payment_details={"credit_card": 67},
        subtotal=59,
        discount_amount=0,
        total_paid=67,
    )
    item = OrderItem(
        item_id="ITEM-1",
        order_id="ORD-1",
        product_id="PROD-1",
        quantity=1,
        unit_price=59,
        item_status=item_status,
    )
    env = CustomerSupportEnvironment(
        CSEnvironmentData(
            products=[product],
            orders=[order],
            order_items=[item],
            customers=[customer],
            warranties=[],
        ),
        now="2026-06-10T10:00:00",
    )
    return env


def test_process_refund_reissues_existing_return_to_new_method_without_goodwill():
    env = _make_env(item_status="delivered", order_status="delivered", shipping_status="delivered")

    env.get_policies({"topic": "return"})
    env.process_return({"item_id": "ITEM-1", "reason": "changed_mind", "confirm": False})
    env.process_return({"item_id": "ITEM-1", "reason": "changed_mind", "confirm": True})

    env.get_policies({"topic": "refund"})
    preview = env.process_refund({"item_id": "ITEM-1", "refund_method": "store_credit", "amount": 59, "confirm": False})
    result = env.process_refund({"item_id": "ITEM-1", "refund_method": "store_credit", "amount": 59, "confirm": True})

    assert preview["status"] == "preview"
    assert result["mode"] == "refund_method_update"
    assert result["refund_amount"] == 59
    assert env.order_items["ITEM-1"].refund_amount == 59
    assert env.order_items["ITEM-1"].refund_method == "store_credit"
    assert env.order_items["ITEM-1"].goodwill_credit == 0


def test_process_refund_reissues_existing_cancel_to_new_method_without_goodwill():
    env = _make_env(item_status="confirmed", order_status="processing", shipping_status="pending")

    env.get_policies({"topic": "cancellation"})
    env.cancel_order({"order_id": "ORD-1", "item_ids": ["ITEM-1"], "confirm": False})
    env.cancel_order({"order_id": "ORD-1", "item_ids": ["ITEM-1"], "confirm": True})

    env.get_policies({"topic": "refund"})
    env.process_refund({"item_id": "ITEM-1", "refund_method": "store_credit", "amount": 59, "confirm": False})
    result = env.process_refund({"item_id": "ITEM-1", "refund_method": "store_credit", "amount": 59, "confirm": True})

    assert result["mode"] == "refund_method_update"
    assert env.order_items["ITEM-1"].refund_amount == 59
    assert env.order_items["ITEM-1"].refund_method == "store_credit"
    assert env.order_items["ITEM-1"].goodwill_credit == 0


def test_process_refund_keeps_additive_credit_when_amount_differs_from_base_refund():
    env = _make_env(item_status="delivered", order_status="delivered", shipping_status="delivered")

    env.get_policies({"topic": "return"})
    env.process_return({"item_id": "ITEM-1", "reason": "changed_mind", "confirm": False})
    env.process_return({"item_id": "ITEM-1", "reason": "changed_mind", "confirm": True})

    env.get_policies({"topic": "refund"})
    env.process_refund({"item_id": "ITEM-1", "refund_method": "store_credit", "amount": 10, "confirm": False})
    result = env.process_refund({"item_id": "ITEM-1", "refund_method": "store_credit", "amount": 10, "confirm": True})

    assert result["mode"] == "goodwill_credit"
    assert result["refund_amount"] == 10
    assert env.order_items["ITEM-1"].refund_amount == 59
    assert env.order_items["ITEM-1"].refund_method == "original_payment"
    assert env.order_items["ITEM-1"].goodwill_credit == 10
    assert env.order_items["ITEM-1"].goodwill_credit_method == "store_credit"


def test_process_return_keeps_mixed_return_and_cancel_order_partially_cancelled():
    env = _make_env(item_status="delivered", order_status="shipped", shipping_status="in_transit")

    second = OrderItem(
        item_id="ITEM-2",
        order_id="ORD-1",
        product_id="PROD-1",
        quantity=1,
        unit_price=59,
        item_status="confirmed",
    )
    env.order_items["ITEM-2"] = second

    env.get_policies({"topic": "cancellation"})
    env.cancel_order({"order_id": "ORD-1", "item_ids": ["ITEM-2"], "confirm": False})
    env.cancel_order({"order_id": "ORD-1", "item_ids": ["ITEM-2"], "confirm": True})

    env.get_policies({"topic": "return"})
    env.process_return({"item_id": "ITEM-1", "reason": "changed_mind", "confirm": False})
    env.process_return({"item_id": "ITEM-1", "reason": "changed_mind", "confirm": True})

    assert env.order_items["ITEM-1"].item_status == "returned"
    assert env.order_items["ITEM-2"].item_status == "cancelled"
    assert env.orders["ORD-1"].status == "partially_cancelled"


def test_process_refund_treats_same_method_top_up_as_supplemental_refund():
    env = _make_env(item_status="delivered", order_status="delivered", shipping_status="damaged")

    env.get_policies({"topic": "return"})
    env.process_return({"item_id": "ITEM-1", "reason": "damaged_in_transit", "confirm": False})
    env.process_return({"item_id": "ITEM-1", "reason": "damaged_in_transit", "confirm": True})

    env.get_policies({"topic": "refund"})
    env.process_refund({"item_id": "ITEM-1", "refund_method": "original_payment", "amount": 67, "confirm": False})
    result = env.process_refund({"item_id": "ITEM-1", "refund_method": "original_payment", "amount": 67, "confirm": True})

    assert result["mode"] == "supplemental_refund"
    assert result["refund_amount"] == 67
    assert env.order_items["ITEM-1"].refund_amount == 59
    assert env.order_items["ITEM-1"].refund_method == "original_payment"
    assert env.order_items["ITEM-1"].goodwill_credit == 0
    assert env.order_items["ITEM-1"].goodwill_credit_method is None


def test_process_refund_allows_multiple_previewed_refunds_and_keeps_shipping_top_up_out_of_goodwill():
    env = _make_env(item_status="delivered", order_status="delivered", shipping_status="damaged")

    env.get_policies({"topic": "return"})
    env.process_return({"item_id": "ITEM-1", "reason": "damaged_in_transit", "confirm": False})
    env.process_return({"item_id": "ITEM-1", "reason": "damaged_in_transit", "confirm": True})

    env.get_policies({"topic": "refund"})
    env.process_refund({"item_id": "ITEM-1", "refund_method": "original_payment", "amount": 8, "confirm": False})
    env.process_refund({"item_id": "ITEM-1", "refund_method": "store_credit", "amount": 15, "confirm": False})
    env.process_refund({"item_id": "ITEM-1", "refund_method": "store_credit", "amount": 10, "confirm": False})

    shipping = env.process_refund({"item_id": "ITEM-1", "refund_method": "original_payment", "amount": 8, "confirm": True})
    late = env.process_refund({"item_id": "ITEM-1", "refund_method": "store_credit", "amount": 15, "confirm": True})
    fragile = env.process_refund({"item_id": "ITEM-1", "refund_method": "store_credit", "amount": 10, "confirm": True})

    assert shipping["mode"] == "supplemental_refund"
    assert shipping["refund_amount"] == 8
    assert late["mode"] == "goodwill_credit"
    assert fragile["mode"] == "goodwill_credit"
    assert env.order_items["ITEM-1"].refund_amount == 59
    assert env.order_items["ITEM-1"].refund_method == "original_payment"
    assert env.order_items["ITEM-1"].goodwill_credit == 25
    assert env.order_items["ITEM-1"].goodwill_credit_method == "store_credit"
