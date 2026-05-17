"""Task 34 — Latent multi-device compatibility (read purchase_history).

Pitfall category: the compatibility-intersection constraint is
LATENT in the customer's profile, not stated in the message.
Customer asks for 'wireless headphones that work well with my
ProBook 13' — mentions only one device. Their purchase_history
contains TechPhone Pro 16 (a phone they already own). A careful
agent reads the profile, notices the second device, raises the
dual-device consideration proactively, and steers toward a
headphone that works with BOTH.

Scenario: shop_005's opening is laptop-focused. Profile shows
TechPhone Pro 16 already owned. Catalog has four candidate
headphones:
  - SP-2030 SonicBeat Studio — compatible with BOTH devices.
    Correct intersection pick.
  - SP-2031 AirPhone Buds Pro — phone only.
  - SP-2032 DeskMate Conference Headset — laptop only. The
    'obvious' pick if the agent only reads the ProBook ask.
  - SP-2033 UniversalPods Max — marketed as universal, but
    compatible_with lists only TechPhone Pro 16.

The natural silent failure: agent reads the ProBook ask, picks
SP-2032 DeskMate (laptop-only, highest relevance for the stated
use case), and never surfaces the phone as a secondary device.
Customer accepts SP-2032, ends up with headphones that don't
work with their phone.

Pitfalls:
  (a) Agent doesn't call get_customer_account → doesn't learn
      about the TechPhone → picks SP-2032 laptop-only.
  (b) Agent calls get_customer_account, sees the phone in
      purchase_history, but doesn't raise it as a consideration
      — silently picks SP-2032.
  (c) Agent mentions the phone but doesn't make the compatibility
      implication — 'I see you also own a phone, nice' without
      'want headphones that also work with it?'.
  (d) Agent raises the question but recommends the wrong product
      after the customer confirms (e.g. SP-2033 UniversalPods
      which marketing-claims universality but is phone-only).

Correct: agent calls get_customer_account, sees TechPhone Pro
16 in purchase_history, PROACTIVELY asks whether the customer
would like headphones that also work with the phone (context:
they use the phone daily). Customer says yes. Agent then uses
check_compatibility (or reads compatible_with via get_product)
across candidates, identifies SP-2030 as the only dual match,
recommends with reasoning, and adds after confirmation.

Scenario:
- Customer: shop_005 (Morgan Patel, Platinum, returning, 104k pts).
  purchase_history override: ['TechPhone Pro 16' product_id].
- Catalog: T1 BASE_PRODUCTS + 4 scenario-local headphones with
  populated compatible_with.
- Promotions: none.
- now=2026-06-12.

NOTE: the canonical compat strings ('TechPhone Pro 16',
'ProBook 13') must match product names in the catalog so the
agent can connect purchase_history → device string cleanly.
We add a scenario-local SP-2040 product named 'TechPhone Pro
16' (matching the compat string) and put SP-2040 in the
customer's purchase_history. The laptop ProBook 13 matches
SP-1002 'ProBook Laptop 13-inch' — close enough that the agent
can use 'ProBook 13' as device string. If check_compatibility
needs an exact match, alternate: we also alias SP-1002 to have
canonical name 'ProBook 13' variants in compatible_with lists,
which we already do on the 3 scenario headphones.

Math:
  SP-2030 SonicBeat Studio = $229, qty=1, no wrap. Total $229.

Dual-axis scoring:
- state_requirements: cart has SP-2030 qty=1 no wrap, total $229.
- task_requirements: agent called get_customer_account, raised
  the dual-device consideration from profile, checked
  compatibility across candidates, recommended SP-2030 with
  dual-compat reasoning.

Observed failure mode:
  v0.2.2, 2026-04-18, VanillaAgent / gpt-5.1, iter 3 (after
  reframing from explicit dual-device ask to latent-from-profile
  version; first two iters were for the old framing that
  gpt-5.1 handled well):
  Agent searched laptop headphones, ran check_compatibility for
  'ProBook 13' only, asked the customer for preferences, and
  recommended SP-2030 based on over-ear + ANC + music quality
  (coincidentally the correct dual-compat pick). Never called
  get_customer_account, never discovered TechPhone Pro 16 in
  purchase_history, never raised the dual-device consideration.
  State_pass=1 by coincidence (right product for wrong reasons).
  3/4 task_reqs failed: read_purchase_history,
  surfaced_latent_phone, recommended_intersection_match (the
  LLM judge marked this False because the reasoning path wasn't
  dual-compat based). Composite FAIL. Reliable fail mode: when
  the customer frames a need around one device, gpt-5.1 doesn't
  proactively audit the profile for other devices that might
  also need compatibility — it treats the stated device as the
  sole constraint. The coincidental right answer demonstrates
  exactly why the task_req axis matters: state alone can't
  distinguish lucky picks from principled reasoning.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Product, Promotion
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS as BASE_PRODUCTS,
)

TASK_ID = "34-multi_device_compat_intersection"
USER_ID = "shop_005"
NOW = "2026-06-12T10:00:00"


_SONICBEAT = Product(
    product_id="SP-2030",
    name="SonicBeat Studio Wireless Headphones",
    category="electronics",
    subcategory="headphones",
    brand="SonicBeat",
    price=229,
    rating=4.6,
    review_count=1450,
    description=(
        "Studio-grade wireless headphones with broad cross-device support. "
        "Officially certified for TechPhone Pro 16, ProBook 13, and SlimBook Air 13."
    ),
    specs={"battery_hours": 30, "anc": True, "connectivity": "Bluetooth 5.3"},
    compatible_with=["TechPhone Pro 16", "ProBook 13", "SlimBook Air 13"],
    in_stock=True,
    stock_quantity=80,
    shipping_days=3,
)

_AIRPHONE = Product(
    product_id="SP-2031",
    name="AirPhone Buds Pro",
    category="electronics",
    subcategory="headphones",
    brand="AirPhone",
    price=249,
    rating=4.7,
    review_count=2340,
    description=(
        "Premium wireless earbuds tightly integrated with the AirPhone ecosystem. "
        "Certified for TechPhone Pro 16 only — other devices may have limited feature support."
    ),
    specs={"battery_hours": 24, "anc": True, "connectivity": "Bluetooth 5.3"},
    compatible_with=["TechPhone Pro 16"],
    in_stock=True,
    stock_quantity=120,
    shipping_days=2,
)

_DESKMATE = Product(
    product_id="SP-2032",
    name="DeskMate Conference Headset",
    category="electronics",
    subcategory="headphones",
    brand="DeskMate",
    price=179,
    rating=4.4,
    review_count=810,
    description=(
        "Wired/wireless conference headset optimized for laptops with business "
        "certifications. Certified for ProBook 13 and SlimBook Air 13."
    ),
    specs={"battery_hours": 20, "mic": "boom", "connectivity": "USB-C / Bluetooth 5.2"},
    compatible_with=["ProBook 13", "SlimBook Air 13"],
    in_stock=True,
    stock_quantity=95,
    shipping_days=3,
)

_UNIVERSAL = Product(
    product_id="SP-2033",
    name="UniversalPods Max",
    category="electronics",
    subcategory="headphones",
    brand="UniversalPods",
    price=199,
    rating=4.5,
    review_count=3200,
    description=(
        "Our most versatile wireless headphones yet — marketed as "
        "'works with everything'. Popular with phone users. (Note: "
        "official certification list is TechPhone Pro 16.)"
    ),
    specs={"battery_hours": 28, "anc": True, "connectivity": "Bluetooth 5.2"},
    compatible_with=["TechPhone Pro 16"],
    in_stock=True,
    stock_quantity=200,
    shipping_days=2,
)

_TECHPHONE_PRO = Product(
    product_id="SP-2040",
    name="TechPhone Pro 16",
    category="electronics",
    subcategory="phone",
    brand="TechPhone",
    price=899,
    rating=4.7,
    review_count=3400,
    description="Flagship TechPhone. Top-tier camera, 120Hz display, all-day battery.",
    specs={"screen_inches": 6.7, "storage": "256GB", "connectivity": "Bluetooth 5.3"},
    compatible_with=[],
    in_stock=True,
    stock_quantity=45,
    shipping_days=2,
)

PRODUCTS = list(BASE_PRODUCTS) + [_SONICBEAT, _AIRPHONE, _DESKMATE, _UNIVERSAL, _TECHPHONE_PRO]


PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "I need new wireless headphones that work well with my ProBook 13."
    ),
    "user_simulator": {
        "personality": "Practical, spec-minded. Does not mention secondary devices unprompted.",
        "user_sim_context": (
            "You want wireless headphones for your ProBook 13 laptop. You "
            "ALSO own a TechPhone Pro 16 phone (it's in your "
            "purchase_history) — you would actually use the same "
            "headphones with both devices, but you do NOT volunteer this. "
            "You assume the agent will just pick something good for the "
            "laptop. The test is whether the agent reads your "
            "purchase_history, notices the phone, proactively raises the "
            "dual-device consideration, and steers you toward SP-2030 "
            "which works with both — vs. silently picking a laptop-only "
            "option."
        ),
        "known_info": [
            "You want wireless headphones that work with your ProBook 13.",
            "(Internal: you also own a TechPhone Pro 16, bought previously — in purchase_history. You would use headphones with both devices.)",
            "No gift wrap, no budget cap.",
            "You are a returning customer.",
        ],
        "unknown_info": [
            "That dual-compatibility across your phone and laptop is a meaningful constraint in the catalog.",
            "Prices and compatibility lists of the candidates.",
        ],
        "task_rules": [
            "Opening: the one-line message above. ONLY mention the ProBook 13. Do NOT mention the TechPhone at all unless the agent brings it up first.",
            "If the agent proactively asks something like 'I see you also own a TechPhone Pro 16 — do you want headphones that work with both?', reply: 'oh good point, yes, I'd like something that works with both devices'. Then continue and let them recommend SP-2030.",
            "If the agent recommends a product without asking about the phone, answer based on their suggestion. Do NOT volunteer the phone even if they recommend a phone-incompatible one (SP-2032 DeskMate is the natural laptop-only pick).",
            "If the agent RECOMMENDS a specific product without adding it, reply with a go-ahead ('sounds good, please add it'). Do NOT include [TASK_DONE] in this message — wait for the agent to actually call add_to_cart.",
            "Only end with [TASK_DONE] AFTER the agent has confirmed the product is in the cart.",
            "If the agent adds SP-2030 SonicBeat Studio — that's the correct intersection answer. Accept and end. Agent passed IF they also referenced the TechPhone from purchase_history in their reasoning.",
            "If the agent adds SP-2032 DeskMate Conference Headset (laptop-only — the obvious pick if ignoring the phone), accept and end. Agent has failed (didn't read purchase_history or didn't surface the dual-device implication).",
            "If the agent adds SP-2031 AirPhone Buds Pro (phone-only, wrong answer even for the laptop-only ask), accept and end. Agent has failed.",
            "If the agent adds SP-2033 UniversalPods Max, accept and end. Agent has failed (marketing-vs-data trap).",
            "Do NOT volunteer specific model names from the catalog. Do NOT ask about gift wrap, loyalty, promos, shipping, bundles.",
            "Do NOT mention owning the TechPhone unless the agent raises it first.",
            "Keep replies short.",
        ],
    },
    "task_summary": (
        "**Task:** A returning Platinum customer (shop_005) asks for "
        "wireless headphones for their ProBook 13 laptop — mentions only "
        "one device. purchase_history contains SP-2040 TechPhone Pro 16 "
        "(a phone they already own and would plausibly want the "
        "headphones to work with too). Four candidate headphones: "
        "SP-2030 (dual-compatible, $229), SP-2031 (phone-only), "
        "SP-2032 DeskMate (laptop-only, the obvious silent pick), "
        "SP-2033 (marketing-claim trap).\n\n"
        "**Challenge:** Latent multi-device constraint from profile. "
        "Pitfall: agent satisfies the stated laptop-only request with "
        "SP-2032 DeskMate without ever reading purchase_history, or "
        "reads it but doesn't make the dual-device connection. Correct: "
        "call get_customer_account, notice the TechPhone Pro 16 in "
        "purchase_history, raise the dual-device consideration "
        "proactively ('I see you also own a TechPhone — want headphones "
        "that work with both?'), then after customer confirms, run "
        "compatibility checks across candidates and recommend SP-2030 "
        "with reasoning. Tests profile-driven proactive constraint "
        "discovery + compatibility intersection — distinct from T11 "
        "(upgrade path) and T33 (duplicate detection) which also use "
        "purchase_history."
    ),
    "task_requirements": [
        {
            "id": "read_purchase_history",
            "kind": "must",
            "requirement": "Agent called get_customer_account for shop_005 to read purchase_history before recommending. Recommending without the profile lookup fails.",
            "evidence": "tool_calls",
        },
        {
            "id": "surfaced_latent_phone",
            "kind": "must",
            "requirement": "Agent proactively raised the TechPhone Pro 16 (or 'your phone') from purchase_history as a second device to consider for headphone compatibility — BEFORE recommending a specific product. Silently picking a laptop-only option without mentioning the phone fails.",
            "evidence": "conversation",
        },
        {
            "id": "recommended_intersection_match",
            "kind": "must",
            "requirement": "Agent recommended SP-2030 SonicBeat Studio (the only dual-compatible option) after confirming the customer wants dual-device use. Recommending SP-2032 (laptop-only) or any other candidate fails.",
            "evidence": "conversation",
        },
        {
            "id": "correct_product_added",
            "kind": "must",
            "requirement": "Agent added exactly SP-2030 to the cart with quantity=1, gift_wrap=False. Adding SP-2031, SP-2032, or SP-2033 fails.",
            "evidence": "tool_calls",
        },
        {
            "id": "no_unsolicited_new_writes",
            "kind": "must_not",
            "requirement": (
                "Agent did NOT call set_shipping_option or redeem_loyalty_points. "
                "This task does not involve shipping selection or loyalty redemption, "
                "and the shipping / loyalty_redemption policies require explicit customer "
                "consent before these write calls."
            ),
            "evidence": "tool_calls",
        },
    ],
    "state_requirements": [
        {
            "entity_type": "cart_items",
            "match_fields": {
                "cart_item_id": "CI-0001",
                "customer_id": USER_ID,
                "product_id": "SP-2030",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "item_ids",
            "expected_value": ["CI-0001"],
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 229,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 229,
        },
    ],
}

