"""Acme Coffee MCP server.

Exposes 6 tools over Streamable HTTP. Run with:
    python -m mcp_server.server

This stands in for the real bootcamp MCP server. On the real day you delete
this folder and point app.config.MCP_SERVER_URL at the URL they give you.
"""
from __future__ import annotations

import logging
import re
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mcp_server import data

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
log = logging.getLogger("acme-mcp")

mcp = FastMCP("acme-coffee")

# Email regex — keep it simple, the LLM is not the validator of last resort.
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


@mcp.tool()
def search_products(
    query: Annotated[str, Field(description="Free-text search across product name and description.")],
    max_results: Annotated[int, Field(description="Maximum products to return (1-10).", ge=1, le=10)] = 5,
) -> list[dict]:
    """Search the Acme Coffee catalogue. Returns matching products with SKU, name, price, and category."""
    q = query.lower().strip()
    if not q:
        return []
    matches = []
    for product in data.PRODUCTS.values():
        haystack = f"{product.name} {product.description} {product.category}".lower()
        if q in haystack:
            matches.append({
                "sku": product.sku,
                "name": product.name,
                "price_usd": product.price_usd,
                "category": product.category,
            })
    log.info("search_products query=%r matches=%d", query, len(matches))
    return matches[:max_results]


@mcp.tool()
def get_product(
    sku: Annotated[str, Field(description="Product SKU, e.g. 'AC-ESP-001'.")],
) -> dict:
    """Return full details for a single product by SKU."""
    product = data.PRODUCTS.get(sku.strip().upper())
    if product is None:
        raise ValueError(f"Unknown SKU: {sku}")
    return {
        "sku": product.sku,
        "name": product.name,
        "description": product.description,
        "price_usd": product.price_usd,
        "category": product.category,
    }


@mcp.tool()
def check_inventory(
    sku: Annotated[str, Field(description="Product SKU to check stock for.")],
) -> dict:
    """Return current stock level for a SKU. units_available=0 means out of stock."""
    sku_norm = sku.strip().upper()
    if sku_norm not in data.PRODUCTS:
        raise ValueError(f"Unknown SKU: {sku}")
    return {"sku": sku_norm, "units_available": data.INVENTORY[sku_norm]}


@mcp.tool()
def place_order(
    sku: Annotated[str, Field(description="Product SKU to order.")],
    quantity: Annotated[int, Field(description="Number of units (1-10).", ge=1, le=10)],
    customer_email: Annotated[str, Field(description="Customer email for confirmation.")],
) -> dict:
    """Place an order. Fails if SKU unknown, stock insufficient, or email malformed."""
    sku_norm = sku.strip().upper()
    if sku_norm not in data.PRODUCTS:
        raise ValueError(f"Unknown SKU: {sku}")
    if not EMAIL_RE.match(customer_email):
        raise ValueError(f"Invalid email format: {customer_email}")
    if data.INVENTORY[sku_norm] < quantity:
        raise ValueError(
            f"Insufficient stock. Requested {quantity}, available {data.INVENTORY[sku_norm]}."
        )
    order = data.create_order(sku_norm, quantity, customer_email)
    log.info("place_order ok order_id=%s sku=%s qty=%d", order.order_id, sku_norm, quantity)
    return {
        "order_id": order.order_id,
        "sku": order.sku,
        "quantity": order.quantity,
        "total_usd": order.total_usd,
        "status": order.status,
        "created_at": order.created_at,
    }


@mcp.tool()
def get_order(
    order_id: Annotated[str, Field(description="Order ID returned by place_order, e.g. 'ORD-A1B2C3D4'.")],
) -> dict:
    """Look up an order by ID."""
    order = data.ORDERS.get(order_id.strip().upper())
    if order is None:
        raise ValueError(f"Order not found: {order_id}")
    return {
        "order_id": order.order_id,
        "sku": order.sku,
        "quantity": order.quantity,
        "customer_email": order.customer_email,
        "status": order.status,
        "total_usd": order.total_usd,
        "created_at": order.created_at,
    }


@mcp.tool()
def cancel_order(
    order_id: Annotated[str, Field(description="Order ID to cancel. Only 'pending' orders can be cancelled.")],
) -> dict:
    """Cancel a pending order. Returns stock to inventory. Fails for shipped/delivered/already-cancelled."""
    order = data.ORDERS.get(order_id.strip().upper())
    if order is None:
        raise ValueError(f"Order not found: {order_id}")
    if order.status != "pending":
        raise ValueError(f"Cannot cancel order in status '{order.status}'. Only 'pending' orders can be cancelled.")
    order.status = "cancelled"
    data.INVENTORY[order.sku] += order.quantity
    log.info("cancel_order ok order_id=%s", order.order_id)
    return {"order_id": order.order_id, "status": order.status}


if __name__ == "__main__":
    # Streamable HTTP transport on port 8765. The agent connects to /mcp.
    log.info("Starting Acme Coffee MCP server on http://127.0.0.1:8765/mcp")
    mcp.run(transport="streamable-http")
