"""JSON for the Next.js frontend. The HTML routes keep the same behavior."""

from __future__ import annotations

from app.catalog import Catalog
from app.filters import Preferences, candidate_pool, parse_preferences
from app.pages import budget_edges_text
from app.ranker import FALLBACK_NOTICE, rank


def location_choices(catalog: Catalog) -> list[str]:
    """City-wide choices first, then every stored neighborhood."""
    names = ["Bangalore", "Bengaluru"]
    seen = {name.casefold() for name in names}
    for location in catalog.locations:
        key = location.casefold()
        if key in seen:
            continue
        seen.add(key)
        names.append(location)
    return names


def meta_payload(catalog: Catalog) -> dict[str, object]:
    manifest = catalog.manifest
    return {
        "locations": location_choices(catalog),
        "budgetText": budget_edges_text(manifest),
        "costP33": manifest.cost_p33,
        "costP66": manifest.cost_p66,
    }


def recommendation_payload(catalog: Catalog, payload: object) -> tuple[dict[str, object], int]:
    """Validate, filter, and rank. The status is 400 when the body is not a valid form."""
    if not isinstance(payload, dict):
        return {"errors": ["Send a JSON object."]}, 400
    form = {key: _text(payload.get(key, "")) for key in ("location", "budget", "cuisine", "min_rating", "extra")}
    preferences, errors = parse_preferences(form)
    if preferences is None:
        return {"errors": errors}, 400
    pool = candidate_pool(catalog.read_restaurants(), catalog.manifest, preferences)
    if not pool:
        return {"empty": True, "preferences": _preferences(preferences), "cards": []}, 200
    ranking = rank(pool, preferences)
    notice = FALLBACK_NOTICE if ranking.source == "fallback" else ""
    summary = ranking.summary.strip() if ranking.source == "model" else ""
    return {
        "empty": False,
        "source": ranking.source,
        "summary": summary,
        "notice": notice,
        "preferences": _preferences(preferences),
        "cards": [_card(card.restaurant, card.explanation, card.explanation_from) for card in ranking.cards],
    }, 200


def _preferences(preferences: Preferences) -> dict[str, str]:
    return {
        "location": preferences.location,
        "budget": preferences.budget,
        "cuisine": preferences.cuisine,
        "minRating": format(preferences.min_rating, "g"),
        "extra": preferences.extra,
    }


def _card(restaurant, explanation: str, explanation_from: str) -> dict[str, object]:
    url = restaurant.url if restaurant.url.startswith(("http://", "https://")) else ""
    return {
        "name": restaurant.name,
        "url": url,
        "cuisines": list(restaurant.cuisines),
        "rating": restaurant.rating,
        "votes": restaurant.votes,
        "costForTwo": restaurant.cost_for_two,
        "location": restaurant.location,
        "onlineOrder": restaurant.online_order,
        "bookTable": restaurant.book_table,
        "explanation": explanation,
        "explanationFrom": explanation_from,
    }


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value)
