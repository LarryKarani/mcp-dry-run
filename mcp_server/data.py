"""In-memory data store for the Acme Coffee MCP server.

This stands in for whatever backend the real MCP server in your bootcamp
will be talking to (database, REST API, etc.). The MCP layer doesn't care.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

OrderStatus = Literal["pending", "shipped", "delivered", "cancelled"]


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    description: str
    price_usd: float
    category: str


@dataclass
class Order:
    order_id: str
    sku: str
    quantity: int
    customer_email: str
    status: OrderStatus
    created_at: str
    total_usd: float


PRODUCTS: dict[str, Product] = {
    "AC-ESP-001": Product(
        sku="AC-ESP-001",
        name="Acme House Espresso",
        description="Dark roast espresso blend, notes of dark chocolate and toasted hazelnut. 250g whole bean.",
        price_usd=18.50,
        category="espresso",
    ),
    "AC-FIL-002": Product(
        sku="AC-FIL-002",
        name="Ethiopia Yirgacheffe",
        description="Single-origin filter coffee, bright citrus and floral notes. 250g whole bean.",
        price_usd=22.00,
        category="filter",
    ),
    "AC-FIL-003": Product(
        sku="AC-FIL-003",
        name="Colombia Huila",
        description="Balanced filter coffee, caramel sweetness and red apple acidity. 250g whole bean.",
        price_usd=19.50,
        category="filter",
    ),
    "AC-DEC-004": Product(
        sku="AC-DEC-004",
        name="Swiss Water Decaf",
        description="Chemical-free decaf, smooth and full-bodied. 250g whole bean.",
        price_usd=20.00,
        category="decaf",
    ),
    "AC-EQP-005": Product(
        sku="AC-EQP-005",
        name="Acme Hand Grinder",
        description="Conical burr hand grinder. Adjustable grind from espresso to French press.",
        price_usd=89.00,
        category="equipment",
    ),
}

# SKU -> units in stock. AC-FIL-003 starts at 0 to make out-of-stock easy to demo.
INVENTORY: dict[str, int] = {
    "AC-ESP-001": 42,
    "AC-FIL-002": 17,
    "AC-FIL-003": 0,
    "AC-DEC-004": 8,
    "AC-EQP-005": 3,
}

ORDERS: dict[str, Order] = {}


def create_order(sku: str, quantity: int, customer_email: str) -> Order:
    """Create an order, decrement inventory. Caller must have validated stock."""
    product = PRODUCTS[sku]
    order = Order(
        order_id=f"ORD-{uuid4().hex[:8].upper()}",
        sku=sku,
        quantity=quantity,
        customer_email=customer_email,
        status="pending",
        created_at=datetime.now(timezone.utc).isoformat(),
        total_usd=round(product.price_usd * quantity, 2),
    )
    ORDERS[order.order_id] = order
    INVENTORY[sku] -= quantity
    return order


def reset_state() -> None:
    """Test helper. Resets inventory and clears orders."""
    INVENTORY.update({
        "AC-ESP-001": 42,
        "AC-FIL-002": 17,
        "AC-FIL-003": 0,
        "AC-DEC-004": 8,
        "AC-EQP-005": 3,
    })
    ORDERS.clear()
