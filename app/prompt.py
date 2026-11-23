"""Instructions and candidate payload sent to the chat model.

The user message is the preferences plus the candidate array. url and address
are left out. Empty lists and an empty excerpt are sent as empty values.
"""

from __future__ import annotations

import json

from app.catalog import Restaurant
from app.filters import Preferences

SYSTEM_INSTRUCTIONS = """You rank restaurants from the candidate list and explain each pick. Follow these rules:
1. Rank only ids that appear in the candidate array. Do not invent an id.
2. Return a JSON object only, with no markdown, in this shape: {"summary": string, "ranked": [{"id": string, "explanation": string}]}.
3. Write each explanation in one or two sentences.
4. A number in an explanation must be that candidate's rating written to one decimal place, that candidate's votes as an integer, or that candidate's costForTwo as an integer. Do not write any other number. Do not write a rating as a fraction or with a scale such as /5.
5. Mention the extra preference only when that candidate's restTypes, dishesLiked, or reviewExcerpt supports it. Otherwise say the listing does not show that preference.
6. Leave summary as a single sentence about the set, or an empty string.
"""


def candidate_record(restaurant: Restaurant) -> dict:
    """One candidate. url and address are omitted on purpose."""
    return {
        "id": restaurant.id,
        "name": restaurant.name,
        "location": restaurant.location,
        "cuisines": list(restaurant.cuisines),
        "costForTwo": restaurant.cost_for_two,
        "rating": restaurant.rating,
        "votes": restaurant.votes,
        "restTypes": list(restaurant.rest_types),
        "dishesLiked": list(restaurant.dishes_liked),
        "onlineOrder": restaurant.online_order,
        "bookTable": restaurant.book_table,
        "reviewExcerpt": restaurant.review_excerpt,
    }


def build_messages(preferences: Preferences, restaurants: list[Restaurant]) -> list[dict[str, str]]:
    """System rules, then the preferences and the candidate array as JSON."""
    payload = {
        "preferences": {
            "location": preferences.location,
            "budget": preferences.budget,
            "cuisine": preferences.cuisine,
            "minRating": preferences.min_rating,
            "extra": preferences.extra,
        },
        "candidates": [candidate_record(restaurant) for restaurant in restaurants],
    }
    return [
        {"role": "system", "content": SYSTEM_INSTRUCTIONS},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
