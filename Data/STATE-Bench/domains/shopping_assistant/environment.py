"""Stateful shopping assistant environment with tool handlers.

Designed for JIT per-task environments (each task ships its own `task_envs/<id>.json`)
and the dual-axis scoring contract:
- `state_requirements` (deterministic): cart aggregates as `modified` entries,
  cart_items as `created` entries with minimal 5-field records.
- `task_requirements` (LLM-judged): conversational verification of policy
  surfacing, acceptable picks, proactive discovery.

Key behaviors:
- Cart pre-exists empty in every task_env, keyed `CART-<customer_id>`. No
  set_task_cart hack and no on-demand cart creation.
- search_products hard-filters on customer-asserted constraints (price,
  rating, stock, category) and soft-ranks on `query` against name, brand,
  subcategory, description, and spec keys/values. A non-empty query with
  zero matches returns no results (not a silent degrade).
- check_compatibility returns canonical-device list when device name unknown.
- get_cart returns persisted cart state only (no derived promo eligibility).
- No process gates: get_promotions / get_policies / apply_promo are independent.
- All time comparisons use `self.now` (set at env init).
"""

from __future__ import annotations

import re
from typing import Any

from domains.shopping_assistant import policies
from domains.shopping_assistant.policies import POLICY_TEXTS, VALID_POLICY_TOPICS
from domains.shopping_assistant.schemas import (
    Cart,
    CartItem,
    Customer,
    Product,
    Promotion,
    SAEnvironmentData,
)
from state_bench.environment import BaseEnvironment

# ---------------------------------------------------------------------------
# Search ranking constants
# ---------------------------------------------------------------------------

SEARCH_TOP_N: int = 10
QUERY_TOKEN_WEIGHT: int = 2
QUERY_NAME_BRAND_BOOST: int = 5


def _norm_token(s: str) -> str:
    """Lowercase + collapse hyphens/spaces to underscores."""
    return s.lower().replace("-", "_").replace(" ", "_")


def _tokenize(s: str) -> list[str]:
    """Lowercase, split on non-alphanumeric, drop empties and length-1 tokens."""
    return [t for t in re.split(r"[^a-z0-9]+", s.lower()) if len(t) > 1]


def _build_searchable_text(p: Product) -> str:
    """Compose a normalized text blob over which queries rank.

    Includes: name, brand, subcategory, description, and the KEY NAMES and
    non-numeric spec VALUES from `specs` (so queries like "battery" or "ssd"
    can still find a product whose specs mention them). Excludes numeric spec
    values (e.g. "16" wouldn't hit "16GB").

    Deliberately EXCLUDES `tags` — tags were removed from Product so agents
    must work through name/description/specs rather than lean on curated labels.
    """
    parts: list[str] = [p.name.lower(), (p.brand or "").lower()]
    if p.subcategory:
        parts.append(p.subcategory.lower().replace("_", " "))
        parts.append(_norm_token(p.subcategory))
    if p.description:
        parts.append(p.description.lower())
    for spec_key, spec_val in p.specs.items():
        parts.append(spec_key.lower().replace("_", " "))
        parts.append(_norm_token(spec_key))
        sval = str(spec_val)
        if not re.match(r"^\s*\d", sval):
            parts.append(sval.lower())
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------


class ShoppingAssistantEnvironment(BaseEnvironment):
    """Stateful environment for the shopping assistant domain."""

    def __init__(self, env_data: SAEnvironmentData, now: str):
        super().__init__(env_data, now)
        self.products: dict[str, Product] = {p.product_id: p for p in env_data.products}
        self.customers: dict[str, Customer] = {c.customer_id: c for c in env_data.customers}
        self.carts_by_id: dict[str, Cart] = {c.cart_id: c for c in env_data.carts}
        self.cart_items: dict[str, CartItem] = {ci.cart_item_id: ci for ci in env_data.cart_items}
        self.promotions: dict[str, Promotion] = {p.promo_code: p for p in env_data.promotions}

        # Cart-item ID counter — seeded above any pre-existing IDs so creations
        # never collide with pre-populated cart_items in the task_env.
        self._next_ci_seq: int = self._initial_ci_seq()

        # Cache the canonical-device vocabulary derived from products. Used by
        # check_compatibility's discoverability hint.
        self._canonical_devices: list[str] = sorted(
            {d for p in self.products.values() for d in p.compatible_with}
        )

    # -------------------------------------------------------------------
    # Snapshot for state_requirements check
    # -------------------------------------------------------------------

    def get_full_snapshot(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Return mutable entities indexed by type and id.

        Carts, cart_items, and customers mutate during a run (customers via
        loyalty-points redemption). Products and promotions are immutable
        per task_env.

        Deep-copied so subsequent mutations to the env do not alias into the
        returned snapshot (lists/dicts on the dataclasses would otherwise be
        shared references via DictMixin.to_dict).
        """
        import copy

        return {
            "carts": {cid: copy.deepcopy(c.to_dict()) for cid, c in self.carts_by_id.items()},
            "cart_items": {ciid: copy.deepcopy(ci.to_dict()) for ciid, ci in self.cart_items.items()},
            "customers": {cid: copy.deepcopy(c.to_dict()) for cid, c in self.customers.items()},
        }

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    def _initial_ci_seq(self) -> int:
        max_seq = 0
        for ciid in self.cart_items:
            m = re.match(r"^CI-(\d+)$", ciid)
            if m:
                max_seq = max(max_seq, int(m.group(1)))
        return max_seq + 1

    def _next_cart_item_id(self) -> str:
        ciid = f"CI-{self._next_ci_seq:04d}"
        self._next_ci_seq += 1
        return ciid

    def _resolve_cart(self, customer_id: str) -> Cart | None:
        return self.carts_by_id.get(f"CART-{customer_id}")

    def _items_in_cart(self, cart: Cart) -> list[CartItem]:
        return [self.cart_items[iid] for iid in cart.item_ids if iid in self.cart_items]

    def _find_cart_item(self, cart: Cart, product_id: str) -> CartItem | None:
        for ci in self._items_in_cart(cart):
            if ci.product_id == product_id:
                return ci
        return None

    def _variant_lookup(self, product: Product, variant_id: str | None) -> dict[str, Any] | None:
        """Find a variant dict on `product.variants` by id. Returns None if no variant requested or no match."""
        if not variant_id or not product.variants:
            return None
        for v in product.variants:
            if v.get("variant_id") == variant_id:
                return v
        return None

    def _unit_price(self, ci: CartItem) -> int:
        """Live unit price for a cart_item, accounting for variant price_delta when set."""
        product = self.products[ci.product_id]
        variant = self._variant_lookup(product, ci.variant_id)
        if variant is not None:
            return int(product.price) + int(variant.get("price_delta", 0))
        return int(product.price)

    def _recompute_cart(self, cart: Cart) -> None:
        """Single source of truth for cart aggregates.

        Pulls live unit prices from the products table — cart_items don't
        store prices. Reapplies any active promo so discount_amount stays
        in sync with subtotal changes (e.g., qty updates).
        """
        items = self._items_in_cart(cart)
        cart.subtotal = sum(self._unit_price(ci) * ci.quantity for ci in items)
        cart.gift_wrap_fee = policies.compute_gift_wrap_fee(sum(1 for ci in items if ci.gift_wrap))

        cart.discount_amount = 0
        if cart.applied_promo_codes:
            kept_promos: list[str] = []
            item_categories = sorted({self.products[ci.product_id].category for ci in items})
            total_discount = 0
            for code in cart.applied_promo_codes:
                promo = self.promotions.get(code)
                result = policies.validate_promo(
                    promo_code=code,
                    promo=promo.to_dict() if promo else None,
                    cart_subtotal=cart.subtotal,
                    cart_categories=item_categories,
                    now=self.now,
                )
                if result["valid"]:
                    kept_promos.append(code)
                    total_discount += result["discount_amount"]
            cart.applied_promo_codes = kept_promos
            cart.discount_amount = total_discount

        # Clamp loyalty_discount to the 50%-of-subtotal cap if subtotal has dropped since redemption.
        if cart.loyalty_discount > 0:
            max_discount = int(cart.subtotal * policies.LOYALTY_REDEMPTION_CAP_PCT)
            if cart.loyalty_discount > max_discount:
                cart.loyalty_discount = max(0, max_discount)
                cart.loyalty_points_redeemed = cart.loyalty_discount * policies.LOYALTY_REDEMPTION_RATE_POINTS_PER_DOLLAR

        cart.total = max(0, cart.subtotal + cart.gift_wrap_fee + cart.shipping_cost - cart.discount_amount - cart.loyalty_discount)

    # -------------------------------------------------------------------
    # READ tools
    # -------------------------------------------------------------------

    def search_products(self, params: dict[str, Any]) -> dict[str, Any]:
        """Search the catalog with hard filters + soft ranking.

        Hard filters (exclude): category, min_price, max_price, min_rating, in_stock_only.
        Soft signal (rank): query — matched against name, brand, subcategory,
        description, and spec keys/values. No curated tags; the agent has to
        work through customer-facing fields.

        Behavior:
        - Hard filters empty -> {"products": [], "note": "..."} with guidance.
        - `query` non-empty -> drop products with zero query matches (score=0).
          This mirrors real search: "no matches" is a valid answer; it forces
          the agent to refine the query or relax filters.
        - `query` empty -> all hard-filter-surviving products are returned in
          stable order (by product_id) up to SEARCH_TOP_N.
        """
        query = (params.get("query") or "").strip()
        category = params.get("category")
        min_price = params.get("min_price")
        max_price = params.get("max_price")
        min_rating = params.get("min_rating")
        in_stock_only = bool(params.get("in_stock_only", False))
        sort_by = params.get("sort_by", "relevance")

        # 1. Hard-filter pass.
        candidates: list[Product] = []
        for p in self.products.values():
            if category and p.category != category:
                continue
            if min_price is not None and p.price < int(min_price):
                continue
            if max_price is not None and p.price > int(max_price):
                continue
            if min_rating is not None and p.rating < float(min_rating):
                continue
            if in_stock_only and not p.in_stock:
                continue
            candidates.append(p)

        if not candidates:
            return {
                "products": [],
                "total_found": 0,
                "note": (
                    "No products match the hard filters "
                    "(category / price / rating / stock). "
                    "Try relaxing them and search again."
                ),
            }

        # 2. Soft-rank pass.
        query_tokens = _tokenize(query) if query else []

        scored: list[tuple[int, Product]] = []
        for p in candidates:
            text = _build_searchable_text(p)
            score = 0
            if query_tokens:
                hits = sum(1 for tok in query_tokens if re.search(rf"\b{re.escape(tok)}\b", text))
                score += hits * QUERY_TOKEN_WEIGHT
                name_brand = f"{p.name.lower()} {(p.brand or '').lower()}"
                nb_hits = sum(1 for tok in query_tokens if re.search(rf"\b{re.escape(tok)}\b", name_brand))
                score += nb_hits * QUERY_NAME_BRAND_BOOST
            scored.append((score, p))

        # 2b. Score-0 floor: if the agent supplied a query and nothing matched,
        # return no results rather than degrading to product_id order.
        if query_tokens:
            scored = [(s, p) for s, p in scored if s > 0]
            if not scored:
                return {
                    "products": [],
                    "total_found": 0,
                    "note": (
                        f"No products match the query '{query}'. "
                        "Try broader or different keywords."
                    ),
                }

        # 3. Sort.
        if sort_by == "price_low":
            scored.sort(key=lambda x: x[1].price)
        elif sort_by == "price_high":
            scored.sort(key=lambda x: -x[1].price)
        elif sort_by == "rating":
            scored.sort(key=lambda x: -x[1].rating)
        elif sort_by == "review_count":
            scored.sort(key=lambda x: -x[1].review_count)
        else:
            # Default: rank by score (desc) then rating (desc) as tiebreaker.
            scored.sort(key=lambda x: (-x[0], -x[1].rating))

        results = [
            {
                "product_id": p.product_id,
                "name": p.name,
                "brand": p.brand,
                "category": p.category,
                "subcategory": p.subcategory,
                "price": p.price,
                "rating": p.rating,
                "review_count": p.review_count,
                "in_stock": p.in_stock,
            }
            for _, p in scored[:SEARCH_TOP_N]
        ]
        return {"products": results, "total_found": len(scored)}

    def get_product_details(self, params: dict[str, Any]) -> dict[str, Any]:
        product_id = params.get("product_id", "")
        product = self.products.get(product_id)
        if not product:
            return {"error": f"Product {product_id} not found."}
        result = product.to_dict()
        result["shipping_estimate"] = f"{product.shipping_days} business days (standard)"
        return result

    def get_variants(self, params: dict[str, Any]) -> dict[str, Any]:
        """List variants (color/size/etc) for a product, if any.

        Returns {product_id, product_name, base_price, variants: [...]}.
        For products without variants, returns an empty list and a note.
        """
        product_id = params.get("product_id", "")
        product = self.products.get(product_id)
        if not product:
            return {"error": f"Product {product_id} not found."}
        if not product.variants:
            return {
                "product_id": product_id,
                "product_name": product.name,
                "base_price": product.price,
                "variants": [],
                "note": "This product has no variants; no variant_id is needed for add_to_cart.",
            }
        return {
            "product_id": product_id,
            "product_name": product.name,
            "base_price": product.price,
            "variants": [
                {
                    "variant_id": v["variant_id"],
                    "label": v.get("label", ""),
                    "effective_price": product.price + int(v.get("price_delta", 0)),
                    "in_stock": bool(v.get("in_stock", True)),
                    "stock_quantity": int(v.get("stock_quantity", 0)),
                }
                for v in product.variants
            ],
        }

    def get_customer_account(self, params: dict[str, Any]) -> dict[str, Any]:
        customer_id = params.get("customer_id", "")
        customer = self.customers.get(customer_id)
        if not customer:
            return {"error": f"Customer {customer_id} not found."}
        return customer.to_dict()

    def get_cart(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return cart contents (persisted state only).

        Does not compute promo eligibility — agents should use
        get_promotions + get_customer_account to reason about applicability.
        """
        customer_id = params.get("customer_id", "")
        cart = self._resolve_cart(customer_id)
        if cart is None:
            return {"error": f"No cart for customer {customer_id}."}
        items_view = []
        for ci in self._items_in_cart(cart):
            product = self.products.get(ci.product_id)
            variant = self._variant_lookup(product, ci.variant_id) if product else None
            unit_price = self._unit_price(ci) if product else 0
            item_view = {
                "cart_item_id": ci.cart_item_id,
                "product_id": ci.product_id,
                "product_name": product.name if product else None,
                "quantity": ci.quantity,
                "gift_wrap": ci.gift_wrap,
                "unit_price": unit_price,
                "line_total": unit_price * ci.quantity,
            }
            if ci.variant_id:
                item_view["variant_id"] = ci.variant_id
                item_view["variant_label"] = (variant or {}).get("label") if variant else None
            items_view.append(item_view)
        return {
            "cart_id": cart.cart_id,
            "customer_id": cart.customer_id,
            "items": items_view,
            "subtotal": cart.subtotal,
            "discount_amount": cart.discount_amount,
            "gift_wrap_fee": cart.gift_wrap_fee,
            "loyalty_discount": cart.loyalty_discount,
            "loyalty_points_redeemed": cart.loyalty_points_redeemed,
            "shipping_option": cart.shipping_option,
            "shipping_cost": cart.shipping_cost,
            "total": cart.total,
            "applied_promo_codes": list(cart.applied_promo_codes),
        }

    def check_compatibility(self, params: dict[str, Any]) -> dict[str, Any]:
        """Check whether `device_name` exact-matches any of product.compatible_with.

        On miss with an unknown device name, returns the canonical-device list
        as a discoverability hint so the agent can correct the spelling.
        """
        product_id = params.get("product_id", "")
        device_name = (params.get("device_name") or "").strip()
        product = self.products.get(product_id)
        if not product:
            return {"error": f"Product {product_id} not found."}

        device_lower = device_name.lower()
        for compat in product.compatible_with:
            if compat.lower() == device_lower:
                return {
                    "compatible": True,
                    "product_id": product_id,
                    "device": compat,
                    "reason": f"{product.name} is compatible with {compat}.",
                }

        # Miss. Was the device name even known to the catalog?
        device_known = any(d.lower() == device_lower for d in self._canonical_devices)
        if device_known:
            return {
                "compatible": False,
                "product_id": product_id,
                "device": device_name,
                "reason": (
                    f"{product.name} is not compatible with {device_name}. "
                    f"Compatible devices for this product: "
                    f"{', '.join(product.compatible_with) if product.compatible_with else 'none listed'}."
                ),
            }
        return {
            "compatible": False,
            "product_id": product_id,
            "device": device_name,
            "reason": (
                f"Unknown device name '{device_name}'. "
                f"Canonical devices in this catalog: "
                f"{', '.join(self._canonical_devices) if self._canonical_devices else 'none'}."
            ),
            "canonical_devices": list(self._canonical_devices),
        }

    def browse_recommendations(self, params: dict[str, Any]) -> dict[str, Any]:
        """REMOVED — kept as a stub so any stale schema reference fails loud.

        The shopping domain is intentionally search-only. To test
        recommendation intent, seed the catalog so the correct products
        surface via search_products rather than via a curated shortcut.
        """
        raise RuntimeError(
            "browse_recommendations has been removed. Use search_products."
        )

    def get_promotions(self, params: dict[str, Any]) -> dict[str, Any]:
        """List active promo codes. Optional category filter. No cart coupling."""
        category = params.get("category")
        promos = []
        for p in self.promotions.values():
            if not p.active:
                continue
            if category and p.category_restriction and category not in p.category_restriction:
                continue
            if p.expiry_date:
                # Hide promos that expired before `now`.
                from datetime import datetime as _dt
                if _dt.fromisoformat(self.now) > _dt.fromisoformat(p.expiry_date):
                    continue
            promos.append(p.to_dict())
        return {"promotions": promos}

    def get_policies(self, params: dict[str, Any]) -> dict[str, Any]:
        topic = params.get("topic", "")
        if topic in POLICY_TEXTS:
            return POLICY_TEXTS[topic]
        return {
            "error": f"Unknown policy topic: '{topic}'. Valid topics: {', '.join(VALID_POLICY_TOPICS)}.",
        }

    # -------------------------------------------------------------------
    # WRITE tools
    # -------------------------------------------------------------------

    def add_to_cart(self, params: dict[str, Any]) -> dict[str, Any]:
        """Create a cart_item record for (cart, product). Recompute cart aggregates.

        If the product is already in the cart, increment its quantity instead
        of creating a duplicate cart_item. Quantity limit enforced.

        If the product has variants, a `variant_id` MUST be supplied. Two items
        of the same product but different variants result in separate lines.
        """
        customer_id = params.get("customer_id", "")
        product_id = params.get("product_id", "")
        quantity = int(params.get("quantity", 1) or 1)
        gift_wrap = bool(params.get("gift_wrap", False))
        variant_id = params.get("variant_id") or None

        if quantity <= 0:
            return {"error": "quantity must be a positive integer."}

        cart = self._resolve_cart(customer_id)
        if cart is None:
            return {"error": f"No cart for customer {customer_id}."}

        product = self.products.get(product_id)
        if product is None:
            return {"error": f"Product {product_id} not found."}

        # Variant validation when product has variants.
        variant: dict[str, Any] | None = None
        if product.variants:
            if not variant_id:
                return {
                    "error": (
                        f"{product.name} requires a variant selection. "
                        f"Check product details or variants to see options."
                    )
                }
            variant = self._variant_lookup(product, variant_id)
            if variant is None:
                return {
                    "error": f"Variant '{variant_id}' not found for {product.name}."
                }
            # Variant-level stock check.
            v_in_stock = bool(variant.get("in_stock", True))
            v_qty = int(variant.get("stock_quantity", 0))
            stock = policies.check_stock(v_in_stock, v_qty, quantity)
            if not stock["available"]:
                return {"error": stock["reason"]}
        elif variant_id:
            return {"error": f"{product.name} does not have variants."}
        else:
            stock = policies.check_stock(product.in_stock, product.stock_quantity, quantity)
            if not stock["available"]:
                return {"error": stock["reason"]}

        # Find an existing line matching BOTH product_id and variant_id (None == None).
        existing: CartItem | None = None
        for ci in self._items_in_cart(cart):
            if ci.product_id == product_id and ci.variant_id == variant_id:
                existing = ci
                break

        if existing is not None:
            qcheck = policies.check_quantity_limit(existing.quantity, quantity)
            if not qcheck["allowed"]:
                return {"error": qcheck["reason"]}
            existing.quantity += quantity
            if gift_wrap:
                existing.gift_wrap = True
            self._recompute_cart(cart)
            return {
                "status": "updated",
                "cart_item_id": existing.cart_item_id,
                "product_id": product_id,
                "product_name": product.name,
                "variant_id": existing.variant_id,
                "quantity": existing.quantity,
                "gift_wrap": existing.gift_wrap,
                "cart_subtotal": cart.subtotal,
                "cart_total": cart.total,
            }

        qcheck = policies.check_quantity_limit(0, quantity)
        if not qcheck["allowed"]:
            return {"error": qcheck["reason"]}

        if gift_wrap and not product.gift_wrap_available:
            return {"error": f"Gift wrapping is not available for {product.name}."}

        ci_id = self._next_cart_item_id()
        ci = CartItem(
            cart_item_id=ci_id,
            customer_id=customer_id,
            product_id=product_id,
            quantity=quantity,
            gift_wrap=gift_wrap,
            variant_id=variant_id,
        )
        self.cart_items[ci_id] = ci
        cart.item_ids.append(ci_id)
        self._recompute_cart(cart)

        unit_price = int(product.price) + int((variant or {}).get("price_delta", 0))
        return {
            "status": "added",
            "cart_item_id": ci_id,
            "product_id": product_id,
            "product_name": product.name,
            "variant_id": variant_id,
            "quantity": quantity,
            "gift_wrap": gift_wrap,
            "unit_price": unit_price,
            "cart_subtotal": cart.subtotal,
            "cart_total": cart.total,
        }

    def update_cart_item(self, params: dict[str, Any]) -> dict[str, Any]:
        """Modify quantity and/or gift_wrap for an existing cart_item.

        quantity=0 removes the item (delegates to remove_from_cart semantics).
        At least one of quantity / gift_wrap must be provided.
        """
        customer_id = params.get("customer_id", "")
        product_id = params.get("product_id", "")
        quantity = params.get("quantity")
        gift_wrap = params.get("gift_wrap")

        if quantity is None and gift_wrap is None:
            return {"error": "Provide at least one of quantity, gift_wrap."}

        cart = self._resolve_cart(customer_id)
        if cart is None:
            return {"error": f"No cart for customer {customer_id}."}

        ci = self._find_cart_item(cart, product_id)
        if ci is None:
            return {"error": f"Product {product_id} not in cart."}

        if quantity is not None:
            new_qty = int(quantity)
            if new_qty <= 0:
                return self.remove_from_cart({"customer_id": customer_id, "product_id": product_id})
            qcheck = policies.check_quantity_limit(0, new_qty)
            if not qcheck["allowed"]:
                return {"error": qcheck["reason"]}
            product = self.products.get(product_id)
            if product is not None:
                stock = policies.check_stock(product.in_stock, product.stock_quantity, new_qty)
                if not stock["available"]:
                    return {"error": stock["reason"]}
            ci.quantity = new_qty

        if gift_wrap is not None:
            new_wrap = bool(gift_wrap)
            if new_wrap:
                product = self.products.get(product_id)
                if product is not None and not product.gift_wrap_available:
                    return {"error": f"Gift wrapping is not available for {product.name}."}
            ci.gift_wrap = new_wrap

        self._recompute_cart(cart)
        product = self.products.get(product_id)
        return {
            "status": "updated",
            "cart_item_id": ci.cart_item_id,
            "product_id": product_id,
            "product_name": product.name if product else None,
            "quantity": ci.quantity,
            "gift_wrap": ci.gift_wrap,
            "cart_subtotal": cart.subtotal,
            "cart_total": cart.total,
        }

    def remove_from_cart(self, params: dict[str, Any]) -> dict[str, Any]:
        """Delete the cart_item for (cart, product). Recompute aggregates."""
        customer_id = params.get("customer_id", "")
        product_id = params.get("product_id", "")
        cart = self._resolve_cart(customer_id)
        if cart is None:
            return {"error": f"No cart for customer {customer_id}."}

        ci = self._find_cart_item(cart, product_id)
        if ci is None:
            return {"error": f"Product {product_id} not in cart."}

        cart.item_ids = [iid for iid in cart.item_ids if iid != ci.cart_item_id]
        self.cart_items.pop(ci.cart_item_id, None)
        self._recompute_cart(cart)
        return {
            "status": "removed",
            "cart_id": cart.cart_id,
            "product_id": product_id,
            "cart_subtotal": cart.subtotal,
            "cart_total": cart.total,
        }

    def apply_promo(self, params: dict[str, Any]) -> dict[str, Any]:
        """Validate `promo_code` against current cart and add it to applied codes.

        Multiple promos stack additively: applying a second distinct code adds
        its discount on top of existing ones. Applying the same code twice is
        a no-op (deduped). Validates intrinsic rules (active, expiry, category,
        min_purchase) — does NOT check customer-fit rules; that's the agent's
        responsibility.
        """
        customer_id = params.get("customer_id", "")
        promo_code = params.get("promo_code", "")
        cart = self._resolve_cart(customer_id)
        if cart is None:
            return {"error": f"No cart for customer {customer_id}."}

        if promo_code in cart.applied_promo_codes:
            return {
                "status": "already_applied",
                "promo_code": promo_code,
                "discount_amount": cart.discount_amount,
                "cart_subtotal": cart.subtotal,
                "cart_total": cart.total,
            }

        promo = self.promotions.get(promo_code)
        item_categories = sorted({self.products[ci.product_id].category for ci in self._items_in_cart(cart)})
        result = policies.validate_promo(
            promo_code=promo_code,
            promo=promo.to_dict() if promo else None,
            cart_subtotal=cart.subtotal,
            cart_categories=item_categories,
            now=self.now,
        )
        if not result["valid"]:
            return {"error": result["reason"]}

        cart.applied_promo_codes = [*cart.applied_promo_codes, promo_code]
        self._recompute_cart(cart)
        return {
            "status": "applied",
            "promo_code": promo_code,
            "applied_promo_codes": list(cart.applied_promo_codes),
            "discount_amount": cart.discount_amount,
            "cart_subtotal": cart.subtotal,
            "cart_total": cart.total,
        }

    def remove_promo(self, params: dict[str, Any]) -> dict[str, Any]:
        """Remove a previously applied promo code and recompute totals."""
        customer_id = params.get("customer_id", "")
        promo_code = params.get("promo_code", "")
        cart = self._resolve_cart(customer_id)
        if cart is None:
            return {"error": f"No cart for customer {customer_id}."}

        if promo_code not in cart.applied_promo_codes:
            return {"error": f"Promo code '{promo_code}' is not currently applied to this cart."}

        cart.applied_promo_codes = [c for c in cart.applied_promo_codes if c != promo_code]
        self._recompute_cart(cart)
        return {
            "status": "removed",
            "promo_code": promo_code,
            "applied_promo_codes": list(cart.applied_promo_codes),
            "discount_amount": cart.discount_amount,
            "cart_subtotal": cart.subtotal,
            "cart_total": cart.total,
        }

    def redeem_loyalty_points(self, params: dict[str, Any]) -> dict[str, Any]:
        """Redeem loyalty points for a dollar discount on the current cart total.

        Debits points from customer.loyalty_points. Enforces minimum, balance, and
        50%-of-cart-total cap per the loyalty_redemption policy.
        """
        customer_id = params.get("customer_id", "")
        requested = int(params.get("points") or 0)
        cart = self._resolve_cart(customer_id)
        if cart is None:
            return {"error": f"No cart for customer {customer_id}."}
        customer = self.customers.get(customer_id)
        if customer is None:
            return {"error": f"Customer {customer_id} not found."}
        if cart.subtotal <= 0:
            return {"error": "Cart is empty — cannot redeem points on an empty cart."}
        if cart.loyalty_discount > 0:
            return {
                "error": (
                    f"Points already redeemed on this cart ({cart.loyalty_points_redeemed} pts = "
                    f"${cart.loyalty_discount}). Cancel first to redeem a different amount."
                )
            }
        result = policies.validate_redemption(
            balance=customer.loyalty_points,
            requested_points=requested,
            cart_total=cart.subtotal + cart.gift_wrap_fee - cart.discount_amount,
        )
        if not result["valid"]:
            return {"error": result["reason"]}

        discount = int(result["discount_amount"])
        points_debited = int(result["points_debited"])
        customer.loyalty_points -= points_debited
        cart.loyalty_discount = discount
        cart.loyalty_points_redeemed = points_debited
        self._recompute_cart(cart)
        return {
            "status": "redeemed",
            "points_redeemed": points_debited,
            "discount_applied": discount,
            "remaining_balance": customer.loyalty_points,
            "cart_subtotal": cart.subtotal,
            "cart_total": cart.total,
        }

    def cancel_loyalty_redemption(self, params: dict[str, Any]) -> dict[str, Any]:
        """Reverse a prior loyalty_points redemption on this cart and credit points back."""
        customer_id = params.get("customer_id", "")
        cart = self._resolve_cart(customer_id)
        if cart is None:
            return {"error": f"No cart for customer {customer_id}."}
        customer = self.customers.get(customer_id)
        if customer is None:
            return {"error": f"Customer {customer_id} not found."}
        if cart.loyalty_discount == 0 and cart.loyalty_points_redeemed == 0:
            return {"error": "No loyalty redemption on this cart to cancel."}
        credited = cart.loyalty_points_redeemed
        customer.loyalty_points += credited
        cart.loyalty_discount = 0
        cart.loyalty_points_redeemed = 0
        self._recompute_cart(cart)
        return {
            "status": "cancelled",
            "points_credited": credited,
            "new_balance": customer.loyalty_points,
            "cart_subtotal": cart.subtotal,
            "cart_total": cart.total,
        }

    def get_shipping_options(self, params: dict[str, Any]) -> dict[str, Any]:
        """List available shipping options for the customer's cart with prices and ETAs.

        Does not mutate cart state. Returns each valid option with `option`,
        `cost`, `eta_description`, and an `eligibility` note explaining any
        tier-based free perk or the 5+-item standard override.
        """
        customer_id = params.get("customer_id", "")
        cart = self._resolve_cart(customer_id)
        if cart is None:
            return {"error": f"No cart for customer {customer_id}."}
        customer = self.customers.get(customer_id)
        if customer is None:
            return {"error": f"Customer {customer_id} not found."}

        items = [self.cart_items[iid] for iid in cart.item_ids if iid in self.cart_items]
        total_item_count = sum(ci.quantity for ci in items)
        max_product_shipping_days = max(
            (self.products[ci.product_id].shipping_days for ci in items if ci.product_id in self.products),
            default=0,
        )

        options: list[dict[str, Any]] = []
        for option_name in policies.VALID_SHIPPING_OPTIONS:
            spec = policies.compute_shipping_cost(option_name, customer.tier, total_item_count)
            if option_name == "standard":
                eta_days = max(max_product_shipping_days, 1)
                eta_desc = f"{eta_days} business days"
            elif option_name == "express":
                eta_days = max(max_product_shipping_days - 1, 1)
                eta_desc = f"{eta_days} business days"
            else:  # next_day
                eta_desc = "next business day"

            if option_name == "standard" and total_item_count >= policies.FREE_SHIPPING_ITEM_THRESHOLD:
                eligibility = "free — 5+ items in cart"
            elif option_name == "express" and customer.tier.lower() in ("gold", "platinum"):
                eligibility = f"free — {customer.tier.capitalize()} perk"
            elif option_name == "next_day" and customer.tier.lower() == "platinum":
                eligibility = "free — Platinum perk"
            else:
                eligibility = f"${spec['cost']}"

            options.append(
                {
                    "option": option_name,
                    "cost": spec["cost"],
                    "eta_description": eta_desc,
                    "eligibility": eligibility,
                }
            )

        return {
            "options": options,
            "cart_item_count": total_item_count,
            "customer_tier": customer.tier,
        }

    def set_shipping_option(self, params: dict[str, Any]) -> dict[str, Any]:
        """Set the shipping option on the cart. Validates and writes cart.shipping_cost.

        Recomputes cart totals so cart.total reflects the added shipping cost.
        Customers can switch options freely by calling again; the prior value
        is overwritten.
        """
        customer_id = params.get("customer_id", "")
        option = params.get("option", "")
        cart = self._resolve_cart(customer_id)
        if cart is None:
            return {"error": f"No cart for customer {customer_id}."}
        customer = self.customers.get(customer_id)
        if customer is None:
            return {"error": f"Customer {customer_id} not found."}
        if not cart.item_ids:
            return {"error": "Cart is empty — cannot set shipping on an empty cart."}

        items = [self.cart_items[iid] for iid in cart.item_ids if iid in self.cart_items]
        total_item_count = sum(ci.quantity for ci in items)
        spec = policies.compute_shipping_cost(option, customer.tier, total_item_count)
        if not spec["valid"]:
            return {"error": spec["reason"]}

        cart.shipping_option = option
        cart.shipping_cost = int(spec["cost"])
        self._recompute_cart(cart)
        return {
            "status": "set",
            "shipping_option": option,
            "shipping_cost": cart.shipping_cost,
            "cart_subtotal": cart.subtotal,
            "cart_total": cart.total,
        }


    def validate_promo(self, params: dict[str, Any]) -> dict[str, Any]:
        """Pure read — check whether a promo code would validate against the current cart.

        Checks intrinsic validity only (exists, active, not expired, category
        restriction, min_purchase). Does NOT check customer-fit rules like
        first-time-only — that's the agent's job via get_customer_account.
        """
        customer_id = params.get("customer_id", "")
        promo_code = params.get("promo_code", "")
        cart = self._resolve_cart(customer_id)
        if cart is None:
            return {"valid": False, "reason": f"No cart for customer {customer_id}.", "estimated_discount": 0}

        promo = self.promotions.get(promo_code)
        item_categories = sorted({self.products[ci.product_id].category for ci in self._items_in_cart(cart)})
        result = policies.validate_promo(
            promo_code=promo_code,
            promo=promo.to_dict() if promo else None,
            cart_subtotal=cart.subtotal,
            cart_categories=item_categories,
            now=self.now,
        )
        return {
            "valid": result["valid"],
            "reason": result["reason"],
            "estimated_discount": int(result.get("discount_amount") or 0) if result["valid"] else 0,
        }

    # -------------------------------------------------------------------
    # Tool handler registry
    # -------------------------------------------------------------------

    @property
    def tool_handlers(self) -> dict[str, Any]:
        return {
            # READ
            "search_products": self.search_products,
            "get_product_details": self.get_product_details,
            "get_variants": self.get_variants,
            "get_customer_account": self.get_customer_account,
            "get_cart": self.get_cart,
            "check_compatibility": self.check_compatibility,
            "get_promotions": self.get_promotions,
            "get_policies": self.get_policies,
            "validate_promo": self.validate_promo,
            # WRITE
            "add_to_cart": self.add_to_cart,
            "update_cart_item": self.update_cart_item,
            "remove_from_cart": self.remove_from_cart,
            "apply_promo": self.apply_promo,
            "remove_promo": self.remove_promo,
            "redeem_loyalty_points": self.redeem_loyalty_points,
            "cancel_loyalty_redemption": self.cancel_loyalty_redemption,
            "get_shipping_options": self.get_shipping_options,
            "set_shipping_option": self.set_shipping_option,
        }
