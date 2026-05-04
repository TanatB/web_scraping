import httpx
import asyncio
import random
import pandas as pd

# GraphQL configs for scraping
STORE = "4799d4-07.myshopify.com"
TOKEN = "de96ef6c65f583c7d3d922c59dd018da"
API_VERSION = "2025-07"
GRAPHQL_URL = f"https://{STORE}/api/{API_VERSION}/graphql"
CONCURRENT_COLLECTIONS = 5

# Request headers
HEADERS = {
    "Content-Type": "application/graphql",
    "X-Shopify-Storefront-Access-Token": TOKEN,
    "Accept": "*/*",
    "Origin": "https://www.jdsports.co.th",
    "Referer": "https://www.jdsports.co.th/",
}

PRODUCT_FIELDS = """
  id
  title
  handle
  description
  productType
  vendor
  tags
  priceRange {
    minVariantPrice { amount currencyCode }
    maxVariantPrice { amount currencyCode }
  }
  images(first: 1) {
    nodes { src altText }
  }
  variants(first: 100) {
    nodes {
      id
      title
      availableForSale
      price { amount currencyCode }
      compareAtPrice { amount currencyCode }
      selectedOptions { name value }
    }
  }
"""


def build_collections_query(cursor: str | None = None) -> str:
    after = f', after: "{cursor}"' if cursor else ""
    return f"""
    {{
      collections(first: 250{after}) {{
        edges {{
          node {{ handle title }}
        }}
        pageInfo {{ hasNextPage endCursor }}
      }}
    }}
    """


def build_collection_products_query(handle: str, cursor: str | None = None) -> str:
    after = f', after: "{cursor}"' if cursor else ""
    return f"""
    {{
      collection(handle: "{handle}") {{
        products(first: 250{after}) {{
          edges {{
            node {{
              {PRODUCT_FIELDS}
            }}
          }}
          pageInfo {{ hasNextPage endCursor }}
        }}
      }}
    }}
    """


async def post_query(client: httpx.AsyncClient, query: str) -> dict:
    for attempt in range(1, 4):
        try:
            response = await client.post(GRAPHQL_URL, content=query, headers=HEADERS)
            response.raise_for_status()
            return response.json()
        except (httpx.ReadTimeout, httpx.NetworkError):
            if attempt == 3:
                raise
            wait = 5 * (2 ** (attempt - 1))  # 5s, 10s
            print(f"  Timeout on attempt {attempt}, retrying in {wait}s...")
            await asyncio.sleep(wait)


async def fetch_all_collections(client: httpx.AsyncClient) -> list[str]:
    handles = []
    cursor = None
    while True:
        data = (await post_query(client, build_collections_query(cursor)))["data"]["collections"]
        handles.extend(edge["node"]["handle"] for edge in data["edges"])
        if not data["pageInfo"]["hasNextPage"]:
            break
        cursor = data["pageInfo"]["endCursor"]
        await asyncio.sleep(1.0)
    return handles


def parse_product_to_rows(node: dict) -> list[dict]:
    product_id = node["id"]
    title = node["title"]
    handle = node["handle"]
    description = node.get("description", "")
    product_type = node.get("productType", "")
    vendor = node.get("vendor", "")
    tags = ", ".join(node.get("tags", []))
    min_price = float(node["priceRange"]["minVariantPrice"]["amount"])
    max_price = float(node["priceRange"]["maxVariantPrice"]["amount"])
    currency = node["priceRange"]["minVariantPrice"]["currencyCode"]
    image_url = node["images"]["nodes"][0]["src"] if node["images"]["nodes"] else ""

    rows = []
    for variant in node["variants"]["nodes"]:
        options = {opt["name"]: opt["value"] for opt in variant["selectedOptions"]}
        compare_at = variant.get("compareAtPrice")
        rows.append({
            "product_id": product_id,
            "product_title": title,
            "handle": handle,
            "description": description,
            "product_type": product_type,
            "vendor": vendor,
            "tags": tags,
            "min_price": min_price,
            "max_price": max_price,
            "currency": currency,
            "variant_id": variant["id"],
            "variant_title": variant["title"],
            "size": options.get("Size", ""),
            "color": options.get("Color", ""),
            "variant_price": float(variant["price"]["amount"]),
            "compare_at_price": float(compare_at["amount"]) if compare_at else None,
            "available": variant["availableForSale"],
            "image_url": image_url,
        })
    return rows


async def respectful_delay():
    await asyncio.sleep(2.0 + random.uniform(0.5, 3.0))


async def fetch_collection_rows(
    client: httpx.AsyncClient,
    handle: str,
    semaphore: asyncio.Semaphore,
) -> list[dict]:
    async with semaphore:
        rows = []
        cursor = None
        while True:
            data = await post_query(client, build_collection_products_query(handle, cursor))
            collection = data["data"]["collection"]
            if collection is None:
                break
            page = collection["products"]
            for edge in page["edges"]:
                rows.extend(parse_product_to_rows(edge["node"]))
            if not page["pageInfo"]["hasNextPage"]:
                break
            cursor = page["pageInfo"]["endCursor"]
            await respectful_delay()
        print(f"  [{handle}] {len(rows)} variant rows")
        return rows


def export_dataset(rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    df.to_csv("./datasets/products.csv", index=False)
    df.to_parquet("./datasets/products.parquet", index=False)


async def main(handles: list[str] | None = None):
    async with httpx.AsyncClient(timeout=60.0) as client:
        if handles:
            print(f"Scraping {len(handles)} specified collection(s)...")
        else:
            print("Fetching all collections...")
            handles = await fetch_all_collections(client)
            print(f"Found {len(handles)} collections. Scraping {CONCURRENT_COLLECTIONS} at a time...")

        semaphore = asyncio.Semaphore(CONCURRENT_COLLECTIONS)
        results = await asyncio.gather(
            *[fetch_collection_rows(client, handle, semaphore) for handle in handles]
        )

        seen_variants: set[str] = set()
        all_rows: list[dict] = []
        for collection_rows in results:
            for row in collection_rows:
                if row["variant_id"] not in seen_variants:
                    seen_variants.add(row["variant_id"])
                    all_rows.append(row)

        export_dataset(all_rows)
        print(f"Exported {len(all_rows)} unique variant rows from {len(handles)} collections.")
