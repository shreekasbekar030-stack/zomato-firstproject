"""HTML for the preference form, the fallback list, and the empty state."""

from __future__ import annotations

import html

from app.catalog import Catalog, Manifest
from app.filters import Preferences
from app.ranker import FALLBACK_NOTICE, Ranking

_PAGE_STYLE = """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; font-family: "Segoe UI", sans-serif; color: #f4efe6; background: #100e0c; line-height: 1.45; }
.wrap { max-width: 44rem; margin: 0 auto; padding: 1.4rem 1rem 3rem; }
.top { margin-bottom: 0.4rem; }
h1 { font-size: 1.9rem; line-height: 1.15; margin: 0.2rem 0 0.45rem; }
.mark { margin: 0; font-size: 0.78rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: #e8b84a; }
.edges, .hint { color: #cbbfa8; margin: 0.35rem 0 0; }
form, .empty, .notice, .summary, .card { background: #1c1916; border: 1px solid #3a332b; border-radius: 0.8rem; }
form { margin: 1rem 0 1.25rem; padding: 1rem 1rem 1.1rem; display: grid; gap: 0.15rem 0.9rem; box-shadow: 0 12px 32px rgba(0, 0, 0, 0.28); }
label { display: block; margin: 0.55rem 0 0.25rem; font-weight: 650; }
input, select, textarea { width: 100%; font: inherit; color: #f4efe6; padding: 0.6rem 0.65rem; border: 1px solid #4a433a; border-radius: 0.5rem; background: #26231e; }
option { background: #26231e; color: #f4efe6; }
input:focus, select:focus, textarea:focus, button:focus { outline: 2px solid #e8b84a; outline-offset: 1px; }
button { margin-top: 0.9rem; font: inherit; font-weight: 700; padding: 0.7rem 0.9rem; border: 0; border-radius: 0.55rem; background: #e8b84a; color: #1a1404; cursor: pointer; }
button:hover { background: #f0c96a; }
.errors { color: #fecdd3; background: #3b1820; border: 1px solid #9f1239; border-radius: 0.55rem; padding: 0.7rem 0.9rem 0.7rem 1.6rem; }
.results { margin: 1rem 0 0; }
.results > h2 { margin: 0 0 0.75rem; font-size: 1.2rem; }
.notice, .summary, .empty { padding: 0.85rem 0.95rem; margin: 0 0 0.9rem; }
.notice { color: #e7dfd2; }
.summary { border-color: #166534; background: #13261b; color: #dcfce7; }
.empty h2, .card h2 { margin: 0 0 0.35rem; font-size: 1.2rem; }
.empty p, .card p { margin: 0.2rem 0; }
.cards { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.8rem; }
.cards li { margin: 0; }
.card { padding: 0.95rem 1rem 1.05rem; }
.card .name { font-size: 1.25rem; }
.card .name a { color: #f0c96a; }
.card .cost, .card .rating { font-weight: 650; color: #f7f1e6; }
.card .cuisines, .card .neighborhood, .card .online-order, .card .book-table { color: #d9cbb6; }
.card .explanation { margin-top: 0.6rem; color: #f4efe6; }
@media (min-width: 40rem) {
  form { grid-template-columns: 1fr 1fr; }
  .span { grid-column: 1 / -1; }
}
"""


def render_home(catalog: Catalog) -> str:
    values = {"location": "", "budget": "", "cuisine": "", "min_rating": "", "extra": ""}
    return _page(catalog, values, errors=[])


def render_invalid(catalog: Catalog, form: dict[str, str], errors: list[str]) -> str:
    values = {
        "location": form.get("location", ""),
        "budget": form.get("budget", "").strip().casefold(),
        "cuisine": form.get("cuisine", ""),
        "min_rating": form.get("min_rating", ""),
        "extra": form.get("extra", ""),
    }
    return _page(catalog, values, errors=errors)


def render_empty(catalog: Catalog, preferences: Preferences) -> str:
    return _page(catalog, _values(preferences), errors=[], empty=preferences)


def render_results(catalog: Catalog, preferences: Preferences, ranking: Ranking) -> str:
    return _page(catalog, _values(preferences), errors=[], ranking=ranking)


def budget_edges_text(manifest: Manifest) -> str:
    low = manifest.cost_p33
    high = manifest.cost_p66
    if low is None or high is None:
        return "Budget edges are not available."
    return (
        f"Low is at or under ₹{low} for two. "
        f"Medium is ₹{low}–₹{high} for two. "
        f"High is above ₹{high} for two."
    )


def _values(preferences: Preferences) -> dict[str, str]:
    return {
        "location": preferences.location,
        "budget": preferences.budget,
        "cuisine": preferences.cuisine,
        "min_rating": format(preferences.min_rating, "g"),
        "extra": preferences.extra,
    }


def _page(
    catalog: Catalog,
    values: dict[str, str],
    errors: list[str],
    *,
    ranking: Ranking | None = None,
    empty: Preferences | None = None,
) -> str:
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Find a restaurant</title>",
        f"<style>{_PAGE_STYLE}</style>",
        "</head>",
        '<body><div class="wrap">',
        '<header class="top">',
        '<p class="mark">Restaurant finder</p>',
        "<h1>Find a restaurant</h1>",
        f"<p class=\"edges\">{_esc(budget_edges_text(catalog.manifest))}</p>",
        "</header>",
        _errors(errors),
        _outcome(ranking, empty),
        _form(catalog, values),
        "</div></body></html>",
    ]
    return "".join(parts)


def _form(catalog: Catalog, values: dict[str, str]) -> str:
    budget_options = ['<option value="">Choose a budget</option>']
    for band, label in (("low", "Low"), ("medium", "Medium"), ("high", "High")):
        selected = " selected" if values["budget"] == band else ""
        budget_options.append(f'<option value="{band}"{selected}>{label}</option>')
    return (
        '<form method="post" action="/recommendations#results">'
        "<div>"
        '<label for="location">Location</label>'
        f'<select id="location" name="location">{_location_options(catalog, values["location"])}</select>'
        "</div>"
        "<div>"
        '<label for="budget">Budget</label>'
        f'<select id="budget" name="budget">{"".join(budget_options)}</select>'
        "</div>"
        '<p class="hint span">Bangalore and Bengaluru include every neighborhood.</p>'
        '<div class="span">'
        '<label for="cuisine">Cuisine</label>'
        f'<input id="cuisine" name="cuisine" value="{_esc(values["cuisine"])}">'
        '<p class="hint">Optional. Leave this blank to include every cuisine.</p>'
        "</div>"
        "<div>"
        '<label for="min_rating">Minimum rating</label>'
        f'<input id="min_rating" name="min_rating" inputmode="decimal" value="{_esc(values["min_rating"])}">'
        "</div>"
        '<div class="span">'
        '<label for="extra">Extra preference</label>'
        f'<textarea id="extra" name="extra" rows="2">{_esc(values["extra"])}</textarea>'
        "</div>"
        '<button class="span" type="submit">Find restaurants</button>'
        "</form>"
    )


def _location_options(catalog: Catalog, selected: str) -> str:
    """City-wide choices first, then every stored neighborhood. No free-text field."""
    names = ["Bangalore", "Bengaluru"]
    seen = {name.casefold() for name in names}
    for location in catalog.locations:
        key = location.casefold()
        if key in seen:
            continue
        seen.add(key)
        names.append(location)
    chosen = selected.strip().casefold()
    options = ['<option value="">Choose a location</option>']
    for name in names:
        mark = " selected" if name.casefold() == chosen else ""
        options.append(f'<option value="{_esc(name)}"{mark}>{_esc(name)}</option>')
    return "".join(options)


def _errors(errors: list[str]) -> str:
    if not errors:
        return ""
    items = "".join(f"<li>{_esc(error)}</li>" for error in errors)
    return f'<ul class="errors" id="results">{items}</ul>'


def _outcome(ranking: Ranking | None, empty: Preferences | None) -> str:
    if empty is not None:
        return (
            '<section class="empty" id="results">'
            "<h2>No restaurants match</h2>"
            "<p>No restaurants match location, budget, cuisine, and minimum rating.</p>"
            f"<p>Location: {_esc(empty.location)}</p>"
            f"<p>Budget: {_esc(empty.budget)}</p>"
            f"<p>Cuisine: {_esc(empty.cuisine)}</p>"
            f"<p>Minimum rating: {_esc(format(empty.min_rating, 'g'))}</p>"
            "</section>"
        )
    if ranking is None:
        return ""
    count = len(ranking.cards)
    label = "1 restaurant" if count == 1 else f"{count} restaurants"
    blocks = [
        '<section class="results" id="results">',
        f"<h2>{label}</h2>",
    ]
    if ranking.source == "model" and ranking.summary.strip():
        blocks.append(f'<p class="summary">{_esc(ranking.summary)}</p>')
    if ranking.source == "fallback":
        blocks.append(f'<p class="notice" data-source="fallback">{_esc(FALLBACK_NOTICE)}</p>')
    blocks.append(f'<ol class="cards" data-source="{_esc(ranking.source)}">')
    for card in ranking.cards:
        blocks.append("<li>")
        blocks.append(_card(card.restaurant, card.explanation, card.explanation_from))
        blocks.append("</li>")
    blocks.append("</ol>")
    blocks.append("</section>")
    return "".join(blocks)


def _card(restaurant, explanation: str, explanation_from: str) -> str:
    name = _esc(restaurant.name)
    if restaurant.url.startswith(("http://", "https://")):
        heading = f'<h2 class="name"><a href="{_esc(restaurant.url)}">{name}</a></h2>'
    else:
        heading = f'<h2 class="name">{name}</h2>'
    online = "yes" if restaurant.online_order else "no"
    booking = "yes" if restaurant.book_table else "no"
    return (
        '<article class="card">'
        f"{heading}"
        f'<p class="cuisines">{_esc(", ".join(restaurant.cuisines))}</p>'
        f'<p class="rating">Rated {_esc(format(restaurant.rating, "g"))} from {restaurant.votes} votes</p>'
        f'<p class="cost">About ₹{restaurant.cost_for_two} for two</p>'
        f'<p class="neighborhood">{_esc(restaurant.location)}</p>'
        f'<p class="online-order">Online order: {online}</p>'
        f'<p class="book-table">Table booking: {booking}</p>'
        f'<p class="explanation" data-explanation-from="{_esc(explanation_from)}">{_esc(explanation)}</p>'
        "</article>"
    )


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)
