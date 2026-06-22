"""Refresh price and availability from official retailer product pages.

Usage:
    python scripts/sync_store_catalog.py
    python scripts/sync_store_catalog.py --limit 3

The synchronizer reads public Product JSON-LD and does not copy page content.
It observes a conservative per-domain delay and retains the curated fallback
when a retailer does not expose structured price or stock.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.database import connect, initialize_database  # noqa: E402

USER_AGENT = "DermaScanAI-Catalog/0.1 (+official-product-reference-refresh)"
DOMAIN_DELAYS = {"dermasoft.com.ec": 5.0}
DEFAULT_DELAY = 1.5


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    initialize_database()
    with connect() as connection:
        query = """
            SELECT id, store_id, name, source_url, price, stock
            FROM products
            WHERE external_reference = 1 AND source_url IS NOT NULL
            ORDER BY store_id, id
        """
        products = connection.execute(query).fetchall()
    if args.limit:
        products = products[: args.limit]

    previous_domain = None
    for product in products:
        domain = urlparse(product["source_url"]).netloc.removeprefix("www.")
        if previous_domain:
            time.sleep(DOMAIN_DELAYS.get(previous_domain, DEFAULT_DELAY))
        previous_domain = domain
        try:
            if product["store_id"] in {"dermasoft", "mendieta"}:
                data = read_woocommerce_product(
                    product["store_id"], product["name"], product["source_url"]
                )
            elif product["store_id"] == "dipaso":
                data = read_vtex_product(product["name"], product["source_url"])
            else:
                data = read_product_json_ld(product["source_url"])
            price = data.get("price")
            available = data.get("available")
            verified_at = datetime.now(timezone.utc).date().isoformat()
            with connect() as connection:
                connection.execute(
                    """
                    UPDATE products
                    SET price = ?, stock = ?, verified_at = ?
                    WHERE id = ?
                    """,
                    (
                        float(price) if price is not None else product["price"],
                        int(available) if available is not None else product["stock"],
                        verified_at,
                        product["id"],
                    ),
                )
            print(f"OK {product['id']}: price={price}, available={available}")
        except Exception as exc:
            print(f"SKIP {product['id']}: {exc}")


def read_product_json_ld(url: str) -> dict:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    html = urlopen(request, timeout=30).read().decode("utf-8", "ignore")
    blocks = re.findall(
        r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
        html,
        re.I | re.S,
    )
    for block in blocks:
        try:
            document = json.loads(block.strip())
        except json.JSONDecodeError:
            continue
        for item in walk_json_ld(document):
            item_type = item.get("@type")
            types = item_type if isinstance(item_type, list) else [item_type]
            if "Product" not in types:
                continue
            offers = item.get("offers", {})
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            availability = str(offers.get("availability", "")).lower()
            return {
                "price": offers.get("price") or offers.get("lowPrice"),
                "available": (
                    False
                    if "outofstock" in availability
                    else True
                    if "instock" in availability
                    else None
                ),
            }
    raise ValueError("No Product JSON-LD found")


def read_woocommerce_product(store_id: str, name: str, source_url: str) -> dict:
    domains = {
        "dermasoft": "https://dermasoft.com.ec",
        "mendieta": "https://mendietabeauty.com",
    }
    slug = urlparse(source_url).path.rstrip("/").split("/")[-1]
    url = (
        f"{domains[store_id]}/wp-json/wc/store/v1/products?"
        + urlencode({"slug": slug})
    )
    request = Request(url, headers={"User-Agent": USER_AGENT})
    products = json.load(urlopen(request, timeout=30))
    if not products:
        url = (
            f"{domains[store_id]}/wp-json/wc/store/v1/products?"
            + urlencode({"search": name, "per_page": 10})
        )
        products = json.load(
            urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=30)
        )
    product = next(
        (
            item
            for item in products
            if normalize_url(item.get("permalink", "")) == normalize_url(source_url)
        ),
        products[0] if products else None,
    )
    if not product:
        raise ValueError("Product not found in WooCommerce Store API")
    prices = product.get("prices", {})
    minor_unit = int(prices.get("currency_minor_unit", 2))
    raw_price = prices.get("price")
    return {
        "price": float(raw_price) / (10**minor_unit) if raw_price else None,
        "available": product.get("is_in_stock"),
    }


def read_vtex_product(name: str, source_url: str) -> dict:
    url = (
        "https://www.dipaso.com.ec/api/catalog_system/pub/products/search/?"
        + urlencode({"ft": name, "_from": 0, "_to": 9})
    )
    request = Request(url, headers={"User-Agent": USER_AGENT})
    products = json.load(urlopen(request, timeout=30))
    product = next(
        (
            item
            for item in products
            if normalize_url(item.get("link", "")) == normalize_url(source_url)
        ),
        products[0] if products else None,
    )
    if not product:
        raise ValueError("Product not found in VTEX catalog")
    offer = product["items"][0]["sellers"][0]["commertialOffer"]
    return {
        "price": offer.get("Price"),
        "available": offer.get("AvailableQuantity", 0) > 0,
    }


def normalize_url(url: str) -> str:
    return url.rstrip("/").lower()


def walk_json_ld(value):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from walk_json_ld(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from walk_json_ld(nested)


if __name__ == "__main__":
    main()
