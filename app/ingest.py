"""Build the restaurant catalog from listing rows.

The command writes data/catalog.sqlite. It does not start a server and it does
not call a model. Tests pass a local JSON list and never download the dataset.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DATASET = "ManikaSaini/zomato-restaurant-recommendation"
DEFAULT_OUTPUT = Path("data") / "catalog.sqlite"
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
_INTEGER = re.compile(r"\d+")

RESTAURANT_COLUMNS = (
    "id",
    "name",
    "address",
    "location",
    "listed_cities",
    "cuisines",
    "cost_for_two",
    "rating",
    "votes",
    "rest_types",
    "dishes_liked",
    "online_order",
    "book_table",
    "url",
    "review_excerpt",
)


@dataclass(frozen=True)
class Listing:
    name: str
    address: str
    location: str
    listed_city: str
    cuisines: list[str]
    cost_for_two: int | None
    rating: float | None
    votes: int
    rest_types: list[str]
    dishes_liked: list[str]
    online_order: bool
    book_table: bool
    url: str
    review_excerpt: str
    source_index: int
    rate_raw: str
    rate_parsed: bool


def parse_rating(value: object) -> float | None:
    """First number in the string, when it is between 0 and 5 inclusive."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    match = _NUMBER.search(text)
    if match is None:
        return None
    number = float(match.group())
    if 0 <= number <= 5:
        return number
    return None


def parse_cost(value: object) -> int | None:
    """Strip commas and spaces, then parse an integer. Anything else is null."""
    if value is None:
        return None
    cleaned = str(value).replace(",", "").replace(" ", "")
    if not cleaned or _INTEGER.fullmatch(cleaned) is None:
        return None
    return int(cleaned)


def parse_votes(value: object) -> int:
    """Integer votes. Missing, negative, and non-integers become 0."""
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, int):
        return value if value >= 0 else 0
    if isinstance(value, float):
        if value < 0 or not value.is_integer():
            return 0
        return int(value)
    text = str(value).strip()
    if _INTEGER.fullmatch(text) is None:
        return 0
    return int(text)


def parse_list(value: object) -> list[str]:
    """Split on commas, trim, and drop empty pieces. Case is preserved."""
    if value is None:
        return []
    pieces = []
    seen: set[str] = set()
    for part in str(value).split(","):
        item = part.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        pieces.append(item)
    return pieces


def parse_yes(value: object) -> bool:
    """True only for Yes, ignoring case and surrounding whitespace."""
    if value is None:
        return False
    return str(value).strip().lower() == "yes"


def parse_excerpt(value: object) -> str:
    """First review text, whitespace collapsed, cut at 400 characters."""
    parsed = value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return ""
        try:
            parsed = ast.literal_eval(text)
        except (SyntaxError, ValueError, MemoryError, TypeError):
            return ""
    elif value is None:
        return ""
    if not isinstance(parsed, (list, tuple)) or not parsed:
        return ""
    first = parsed[0]
    if not isinstance(first, (list, tuple)) or len(first) < 2 or first[1] is None:
        return ""
    collapsed = " ".join(str(first[1]).split())
    return collapsed[:400]


def normalize(value: str) -> str:
    """Casefold and collapse internal whitespace. Punctuation stays."""
    return " ".join(value.casefold().split())


def collapse_key(name: str, address: str) -> str:
    return normalize(name) + "\n" + normalize(address)


def restaurant_id(name: str, address: str) -> str:
    digest = hashlib.sha256(collapse_key(name, address).encode("utf-8")).hexdigest()
    return digest[:16]


def parse_listing(row: dict, source_index: int) -> tuple[Listing | None, str, bool]:
    """Return the listing, the raw rate string, and whether that rate parsed.

    A blank name or address returns no listing. The rate result is still
    reported so the manifest can list every rejected string.
    """
    rate_raw = "" if row.get("rate") is None else str(row.get("rate")).strip()
    rating = parse_rating(row.get("rate"))
    name = "" if row.get("name") is None else str(row.get("name")).strip()
    address = "" if row.get("address") is None else str(row.get("address")).strip()
    if not name or not address:
        return None, rate_raw, rating is not None
    location = "" if row.get("location") is None else str(row.get("location")).strip()
    listed = row.get("listed_in(city)")
    listed_city = "" if listed is None else str(listed).strip()
    url = "" if row.get("url") is None else str(row.get("url")).strip()
    listing = Listing(
        name=name,
        address=address,
        location=location,
        listed_city=listed_city,
        cuisines=parse_list(row.get("cuisines")),
        cost_for_two=parse_cost(row.get("approx_cost(for two people)")),
        rating=rating,
        votes=parse_votes(row.get("votes")),
        rest_types=parse_list(row.get("rest_type")),
        dishes_liked=parse_list(row.get("dish_liked")),
        online_order=parse_yes(row.get("online_order")),
        book_table=parse_yes(row.get("book_table")),
        url=url,
        review_excerpt=parse_excerpt(row.get("reviews_list")),
        source_index=source_index,
        rate_raw=rate_raw,
        rate_parsed=rating is not None,
    )
    return listing, rate_raw, rating is not None


def _winner_sort_key(listing: Listing) -> tuple:
    rating = listing.rating
    return (
        listing.votes,
        rating is not None,
        rating if rating is not None else -1.0,
        listing.cost_for_two is not None,
        -listing.source_index,
    )


def _union(groups: list[list[str]]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for group in groups:
        for item in group:
            if item in seen:
                continue
            seen.add(item)
            merged.append(item)
    return merged


def collapse(listings: list[Listing]) -> list[dict]:
    """One restaurant per normalized name and address. Highest votes win."""
    grouped: dict[str, list[Listing]] = {}
    for listing in listings:
        grouped.setdefault(collapse_key(listing.name, listing.address), []).append(listing)
    restaurants: list[dict] = []
    for key, group in grouped.items():
        ordered = sorted(group, key=lambda item: item.source_index)
        winner = max(ordered, key=_winner_sort_key)
        others = [item for item in ordered if item is not winner]
        cities = _union(
            [[winner.listed_city] if winner.listed_city else []]
            + [[item.listed_city] if item.listed_city else [] for item in others]
        )
        restaurants.append(
            {
                "id": hashlib.sha256(key.encode("utf-8")).hexdigest()[:16],
                "name": winner.name,
                "address": winner.address,
                "location": winner.location,
                "listed_cities": cities,
                "cuisines": _union([winner.cuisines] + [item.cuisines for item in others]),
                "cost_for_two": winner.cost_for_two,
                "rating": winner.rating,
                "votes": winner.votes,
                "rest_types": _union([winner.rest_types] + [item.rest_types for item in others]),
                "dishes_liked": _union([winner.dishes_liked] + [item.dishes_liked for item in others]),
                "online_order": any(item.online_order for item in ordered),
                "book_table": any(item.book_table for item in ordered),
                "url": winner.url,
                "review_excerpt": winner.review_excerpt,
            }
        )
    return restaurants


def budget_edges(costs: list[int]) -> tuple[int | None, int | None]:
    """Nearest-rank 33rd and 66th percentiles. An empty list leaves both null."""
    if not costs:
        return None, None
    ordered = sorted(costs)
    return _nearest_rank(ordered, 33), _nearest_rank(ordered, 66)


def _nearest_rank(ordered: list[int], percent: int) -> int:
    rank = math.ceil(percent / 100 * len(ordered))
    return ordered[rank - 1]


def build_catalog(rows: list[dict]) -> tuple[list[dict], dict]:
    listings: list[Listing] = []
    dropped = 0
    unparsed: list[str] = []
    seen_unparsed: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise SystemExit("each listing must be a JSON object")
        listing, rate_raw, parsed = parse_listing(row, index)
        if not parsed and rate_raw not in seen_unparsed:
            seen_unparsed.add(rate_raw)
            unparsed.append(rate_raw)
        if listing is None:
            dropped += 1
            continue
        listings.append(listing)
    restaurants = collapse(listings)
    costs = [item["cost_for_two"] for item in restaurants if item["cost_for_two"] is not None]
    low, high = budget_edges(costs)
    manifest = {
        "dataset": DATASET,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "source_rows": len(rows),
        "restaurant_count": len(restaurants),
        "dropped_blank_identity": dropped,
        "missing_rating": sum(1 for item in restaurants if item["rating"] is None),
        "missing_cost": sum(1 for item in restaurants if item["cost_for_two"] is None),
        "unparsed_rate_values": unparsed,
        "cost_p33": low,
        "cost_p66": high,
    }
    return restaurants, manifest


def write_catalog(path: Path, restaurants: list[dict], manifest: dict) -> None:
    """Replace the catalog only after the new tables commit."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    connection = sqlite3.connect(temporary)
    try:
        connection.execute("BEGIN")
        connection.execute(
            """
            CREATE TABLE restaurants (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                address TEXT NOT NULL,
                location TEXT NOT NULL,
                listed_cities TEXT NOT NULL,
                cuisines TEXT NOT NULL,
                cost_for_two INTEGER,
                rating REAL,
                votes INTEGER NOT NULL,
                rest_types TEXT NOT NULL,
                dishes_liked TEXT NOT NULL,
                online_order INTEGER NOT NULL,
                book_table INTEGER NOT NULL,
                url TEXT NOT NULL,
                review_excerpt TEXT NOT NULL
            )
            """
        )
        connection.execute("CREATE INDEX idx_restaurants_location ON restaurants(location)")
        connection.execute("CREATE INDEX idx_restaurants_rating ON restaurants(rating)")
        connection.execute("CREATE INDEX idx_restaurants_cost ON restaurants(cost_for_two)")
        connection.execute(
            """
            CREATE TABLE manifest (
                dataset TEXT NOT NULL,
                built_at TEXT NOT NULL,
                source_rows INTEGER NOT NULL,
                restaurant_count INTEGER NOT NULL,
                dropped_blank_identity INTEGER NOT NULL,
                missing_rating INTEGER NOT NULL,
                missing_cost INTEGER NOT NULL,
                unparsed_rate_values TEXT NOT NULL,
                cost_p33 INTEGER,
                cost_p66 INTEGER
            )
            """
        )
        connection.executemany(
            f"INSERT INTO restaurants ({', '.join(RESTAURANT_COLUMNS)}) VALUES ({', '.join('?' for _ in RESTAURANT_COLUMNS)})",
            [_restaurant_row(item) for item in restaurants],
        )
        connection.execute(
            """
            INSERT INTO manifest (
                dataset, built_at, source_rows, restaurant_count, dropped_blank_identity,
                missing_rating, missing_cost, unparsed_rate_values, cost_p33, cost_p66
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                manifest["dataset"],
                manifest["built_at"],
                manifest["source_rows"],
                manifest["restaurant_count"],
                manifest["dropped_blank_identity"],
                manifest["missing_rating"],
                manifest["missing_cost"],
                json.dumps(manifest["unparsed_rate_values"]),
                manifest["cost_p33"],
                manifest["cost_p66"],
            ),
        )
        connection.commit()
    except Exception:
        connection.close()
        temporary.unlink(missing_ok=True)
        raise
    connection.close()
    os.replace(temporary, path)


def _restaurant_row(item: dict) -> tuple:
    return (
        item["id"],
        item["name"],
        item["address"],
        item["location"],
        json.dumps(item["listed_cities"]),
        json.dumps(item["cuisines"]),
        item["cost_for_two"],
        item["rating"],
        item["votes"],
        json.dumps(item["rest_types"]),
        json.dumps(item["dishes_liked"]),
        1 if item["online_order"] else 0,
        1 if item["book_table"] else 0,
        item["url"],
        item["review_excerpt"],
    )


def load_rows_file(path: Path) -> list[dict]:
    if not path.is_file():
        raise SystemExit(f"rows file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"rows file is not valid JSON: {path}") from exc
    if not isinstance(payload, list):
        raise SystemExit("rows file must be a JSON list")
    return payload


def load_train_split() -> list[dict]:
    """Download the train split. Callers that pass --rows-file never reach this."""
    from datasets import load_dataset

    dataset = load_dataset(DATASET, split="train")
    return [dict(row) for row in dataset]


def ingest(rows: list[dict], output: Path) -> dict:
    restaurants, manifest = build_catalog(rows)
    write_catalog(output, restaurants, manifest)
    return manifest


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build data/catalog.sqlite from listing rows.")
    parser.add_argument("--rows-file", type=Path, help="Local JSON list. Omit this to load the Hugging Face train split.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Catalog path. Defaults to data/catalog.sqlite.")
    args = parser.parse_args(argv)
    rows = load_rows_file(args.rows_file) if args.rows_file is not None else load_train_split()
    manifest = ingest(rows, args.output)
    json.dump(manifest, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
