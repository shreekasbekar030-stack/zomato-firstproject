"""Read the restaurant catalog that ingest wrote.

The server loads the file once. A request uses that copy, so a later ingest
does not change a process that is already running.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

CATALOG_PATH = Path("data") / "catalog.sqlite"


@dataclass(frozen=True)
class Restaurant:
    id: str
    name: str
    address: str
    location: str
    listed_cities: list[str]
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


@dataclass(frozen=True)
class Manifest:
    dataset: str
    built_at: str
    source_rows: int
    restaurant_count: int
    dropped_blank_identity: int
    missing_rating: int
    missing_cost: int
    unparsed_rate_values: list[str]
    cost_p33: int | None
    cost_p66: int | None


class Catalog:
    """Restaurants and budget edges kept for the life of the process."""

    def __init__(self, restaurants: list[Restaurant], manifest: Manifest) -> None:
        self.manifest = manifest
        self.locations = tuple(
            sorted({item.location for item in restaurants if item.location}, key=str.casefold)
        )
        self._restaurants = list(restaurants)
        self.reads = 0

    def read_restaurants(self) -> list[Restaurant]:
        """Return the restaurants loaded at startup. Each call is one read."""
        self.reads += 1
        return list(self._restaurants)


def load_catalog(path: Path = CATALOG_PATH) -> Catalog:
    """Open a catalog file. Exit when the file, the manifest, or the rows are unusable."""
    if not path.is_file():
        raise SystemExit(f"catalog not found: {path}")
    try:
        connection = sqlite3.connect(path)
    except sqlite3.Error as exc:
        raise SystemExit(f"catalog cannot be opened: {path}") from exc
    try:
        try:
            manifest_row = connection.execute(
                """
                SELECT dataset, built_at, source_rows, restaurant_count, dropped_blank_identity,
                       missing_rating, missing_cost, unparsed_rate_values, cost_p33, cost_p66
                FROM manifest
                """
            ).fetchone()
            restaurant_rows = connection.execute(
                """
                SELECT id, name, address, location, listed_cities, cuisines, cost_for_two,
                       rating, votes, rest_types, dishes_liked, online_order, book_table,
                       url, review_excerpt
                FROM restaurants
                """
            ).fetchall()
        except sqlite3.Error as exc:
            raise SystemExit(f"catalog cannot be opened: {path}") from exc
    finally:
        connection.close()
    if manifest_row is None:
        raise SystemExit(f"catalog manifest is missing: {path}")
    manifest = _manifest(manifest_row)
    if manifest.restaurant_count <= 0:
        raise SystemExit(f"catalog has no restaurants: {path}")
    try:
        restaurants = [_restaurant(row) for row in restaurant_rows]
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise SystemExit(f"catalog cannot be opened: {path}") from exc
    return Catalog(restaurants, manifest)


def _manifest(row: tuple) -> Manifest:
    return Manifest(
        dataset=str(row[0]),
        built_at=str(row[1]),
        source_rows=int(row[2]),
        restaurant_count=int(row[3]),
        dropped_blank_identity=int(row[4]),
        missing_rating=int(row[5]),
        missing_cost=int(row[6]),
        unparsed_rate_values=_string_list(row[7]),
        cost_p33=None if row[8] is None else int(row[8]),
        cost_p66=None if row[9] is None else int(row[9]),
    )


def _restaurant(row: tuple) -> Restaurant:
    return Restaurant(
        id=str(row[0]),
        name=str(row[1]),
        address=str(row[2]),
        location=str(row[3]),
        listed_cities=_string_list(row[4]),
        cuisines=_string_list(row[5]),
        cost_for_two=None if row[6] is None else int(row[6]),
        rating=None if row[7] is None else float(row[7]),
        votes=int(row[8]),
        rest_types=_string_list(row[9]),
        dishes_liked=_string_list(row[10]),
        online_order=bool(row[11]),
        book_table=bool(row[12]),
        url=str(row[13]),
        review_excerpt=str(row[14]),
    )


def _string_list(value: object) -> list[str]:
    parsed = json.loads(str(value))
    if not isinstance(parsed, list) or any(not isinstance(item, str) for item in parsed):
        raise TypeError("catalog field is not a JSON array of strings")
    return list(parsed)
