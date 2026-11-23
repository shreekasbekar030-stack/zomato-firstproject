"""Hard filters for location, budget, cuisine, and minimum rating.

The extra preference is not an argument here. Online order and table booking
are not filters.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from app.catalog import Manifest, Restaurant

POOL_LIMIT = 20
_CITY_ALIASES = frozenset({"bangalore", "bengaluru"})
_BANDS = frozenset({"low", "medium", "high"})


@dataclass(frozen=True)
class Preferences:
    location: str
    budget: str
    cuisine: str
    min_rating: float
    extra: str


def parse_preferences(form: Mapping[str, str]) -> tuple[Preferences | None, list[str]]:
    """Validate a submitted form. Every invalid field is reported."""
    errors: list[str] = []
    location = str(form.get("location", "")).strip()
    if not location:
        errors.append("Enter a location.")
    elif len(location) > 80:
        errors.append("Location must be at most 80 characters.")

    budget = str(form.get("budget", "")).strip().casefold()
    if budget not in _BANDS:
        errors.append("Budget must be low, medium, or high.")

    cuisine = str(form.get("cuisine", "")).strip()
    if len(cuisine) > 40:
        errors.append("Cuisine must be at most 40 characters.")

    rating_text = str(form.get("min_rating", "")).strip()
    minimum: float | None
    try:
        minimum = float(rating_text)
    except ValueError:
        minimum = None
    if minimum is None or not math.isfinite(minimum) or minimum < 0 or minimum > 5:
        errors.append("Minimum rating must be a number from 0 to 5.")
        minimum = None

    extra = str(form.get("extra", "")).strip()
    if len(extra) > 200:
        errors.append("Extra preference must be at most 200 characters.")

    if errors or minimum is None or budget not in _BANDS:
        return None, errors
    return Preferences(location, budget, cuisine, minimum, extra), []


def candidate_pool(
    restaurants: list[Restaurant],
    manifest: Manifest,
    preferences: Preferences,
) -> list[Restaurant]:
    """Restaurants that pass every hard filter, capped at the candidate pool."""
    matched = [
        restaurant
        for restaurant in matching_location(restaurants, preferences.location)
        if matching_budget(restaurant.cost_for_two, preferences.budget, manifest)
        and matching_cuisine(restaurant.cuisines, preferences.cuisine)
        and matching_rating(restaurant.rating, preferences.min_rating)
    ]
    matched.sort(key=_sort_key)
    return matched[:POOL_LIMIT]


def matching_location(restaurants: list[Restaurant], query: str) -> list[Restaurant]:
    """City aliases first, then an exact neighborhood, then an exact listing city."""
    key = query.strip().casefold()
    if key in _CITY_ALIASES:
        return list(restaurants)
    neighborhood = [item for item in restaurants if item.location.strip().casefold() == key]
    if neighborhood:
        return neighborhood
    return [
        item
        for item in restaurants
        if any(city.strip().casefold() == key for city in item.listed_cities)
    ]


def matching_budget(cost: int | None, band: str, manifest: Manifest) -> bool:
    """Compare a cost for two with the manifest edges. A null cost matches nothing."""
    low = manifest.cost_p33
    high = manifest.cost_p66
    if cost is None or low is None or high is None:
        return False
    if band == "low":
        return cost <= low
    if band == "medium":
        return low < cost <= high
    if band == "high":
        return cost > high
    return False


def matching_cuisine(cuisines: list[str], query: str) -> bool:
    """Case-insensitive substring of the joined cuisine list.

    A blank query does not filter. A named cuisine does not match an empty list.
    """
    needle = query.strip().casefold()
    if not needle:
        return True
    if not cuisines:
        return False
    return needle in ", ".join(cuisines).casefold()


def matching_rating(rating: float | None, minimum: float) -> bool:
    """Keep a parsed rating at or above the minimum. Null ratings drop out."""
    return rating is not None and rating >= minimum


def _sort_key(restaurant: Restaurant) -> tuple:
    rating = restaurant.rating if restaurant.rating is not None else -1.0
    return (-rating, -restaurant.votes, restaurant.name, restaurant.id)
