"""Phase 1 filters and the template page. No dataset download and no model call."""

import socket
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.catalog import Catalog, Manifest, Restaurant, load_catalog
from app.filters import POOL_LIMIT, Preferences, candidate_pool, parse_preferences
from app.ingest import ingest
from app.main import create_app, main
from app.ranker import FALLBACK_NOTICE, rank, template_explanation


def test_city_aliases_keep_every_restaurant_including_a_blank_neighborhood() -> None:
    restaurants = [
        place("1", "Alpha", location="Banashankari"),
        place("2", "Blank", location=""),
        place("3", "South", location="Jayanagar"),
    ]
    for query in ("bangalore", "BANGALORE", " bangalore ", "bengaluru", "Bengaluru"):
        found = _names(candidate_pool(restaurants, _manifest(), _prefs(location=query, min_rating=0)))
        assert found == ["Alpha", "Blank", "South"]


def test_exact_neighborhood_beats_a_listing_city_with_the_same_text() -> None:
    restaurants = [
        place("1", "Here", location="Banashankari", listed_cities=["Somewhere"]),
        place("2", "Listed", location="Jayanagar", listed_cities=["Banashankari"]),
    ]
    found = candidate_pool(restaurants, _manifest(), _prefs(location="banashankari"))
    assert _names(found) == ["Here"]


def test_listing_city_matches_when_no_neighborhood_does() -> None:
    restaurants = [
        place("1", "Listed", location="", listed_cities=["South Bangalore"]),
        place("2", "Other", location="Jayanagar", listed_cities=["Banashankari"]),
    ]
    found = candidate_pool(restaurants, _manifest(), _prefs(location="south bangalore"))
    assert _names(found) == ["Listed"]


def test_unknown_prefix_street_and_other_city_match_nothing() -> None:
    restaurants = [
        place("1", "Jalsa", location="Banashankari", address="12, Main Road", listed_cities=["South Bangalore"]),
    ]
    manifest = _manifest()
    for query in ("Banas", "Main Road", "Mumbai", "bangalore south", "greater bangalore"):
        assert candidate_pool(restaurants, manifest, _prefs(location=query)) == []


def test_a_blank_neighborhood_is_kept_only_by_an_alias_or_its_listing_city() -> None:
    restaurants = [place("1", "Blank", location="", listed_cities=["Jayanagar"])]
    manifest = _manifest()
    assert candidate_pool(restaurants, manifest, _prefs(location="Banashankari")) == []
    assert _names(candidate_pool(restaurants, manifest, _prefs(location="Jayanagar"))) == ["Blank"]


def test_budget_bands_follow_the_manifest_edges() -> None:
    restaurants = [
        place("low-edge", "At low", cost_for_two=100),
        place("below", "Below", cost_for_two=99),
        place("mid", "Middle", cost_for_two=150),
        place("high-edge", "At high", cost_for_two=200),
        place("above", "Above", cost_for_two=201),
        place("none", "No cost", cost_for_two=None),
    ]
    manifest = _manifest(cost_p33=100, cost_p66=200)
    assert _names(candidate_pool(restaurants, manifest, _prefs(budget="low"))) == ["At low", "Below"]
    assert _names(candidate_pool(restaurants, manifest, _prefs(budget="medium"))) == ["At high", "Middle"]
    assert _names(candidate_pool(restaurants, manifest, _prefs(budget="high"))) == ["Above"]


def test_equal_edges_leave_medium_empty() -> None:
    restaurants = [
        place("1", "Edge", cost_for_two=100),
        place("2", "Over", cost_for_two=101),
    ]
    manifest = _manifest(cost_p33=100, cost_p66=100)
    assert _names(candidate_pool(restaurants, manifest, _prefs(budget="low"))) == ["Edge"]
    assert candidate_pool(restaurants, manifest, _prefs(budget="medium")) == []
    assert _names(candidate_pool(restaurants, manifest, _prefs(budget="high"))) == ["Over"]


def test_null_edges_match_no_budget() -> None:
    restaurants = [place("1", "Priced", cost_for_two=100)]
    assert candidate_pool(restaurants, _manifest(cost_p33=None, cost_p66=None), _prefs()) == []


def test_cuisine_match_is_a_substring_and_an_empty_list_drops_out() -> None:
    restaurants = [
        place("1", "Chinese place", cuisines=["North Indian", "Chinese"]),
        place("2", "Empty", cuisines=[]),
    ]
    manifest = _manifest()
    assert _names(candidate_pool(restaurants, manifest, _prefs(cuisine="chinese"))) == ["Chinese place"]
    assert _names(candidate_pool(restaurants, manifest, _prefs(cuisine="Indian"))) == ["Chinese place"]
    assert candidate_pool(restaurants, manifest, _prefs(cuisine="Thai")) == []
    assert _names(candidate_pool(restaurants, manifest, _prefs(cuisine=""))) == ["Chinese place", "Empty"]


def test_rating_floor_keeps_equal_ratings_and_drops_null() -> None:
    restaurants = [
        place("1", "Equal", rating=4.0),
        place("2", "Under", rating=3.9),
        place("3", "Zero", rating=0.0),
        place("4", "Top", rating=5.0),
        place("5", "Missing", rating=None),
    ]
    manifest = _manifest()
    assert "Equal" in _names(candidate_pool(restaurants, manifest, _prefs(min_rating=4)))
    assert "Under" not in _names(candidate_pool(restaurants, manifest, _prefs(min_rating=4)))
    assert "Missing" not in _names(candidate_pool(restaurants, manifest, _prefs(min_rating=0)))
    assert _names(candidate_pool(restaurants, manifest, _prefs(min_rating=0))) == ["Top", "Equal", "Under", "Zero"]
    assert _names(candidate_pool(restaurants, manifest, _prefs(min_rating=5))) == ["Top"]


def test_sort_is_rating_then_votes_then_name_then_id() -> None:
    restaurants = [
        place("b", "Apple", rating=4.0, votes=10),
        place("a", "Apple", rating=4.0, votes=10),
        place("c", "Mango", rating=4.0, votes=10),
        place("d", "Higher", rating=4.0, votes=12),
        place("e", "Best", rating=4.8, votes=1),
    ]
    found = candidate_pool(restaurants, _manifest(), _prefs(min_rating=0))
    assert _names(found) == ["Best", "Higher", "Apple", "Apple", "Mango"]
    assert [item.id for item in found if item.name == "Apple"] == ["a", "b"]


def test_pool_keeps_twenty_and_the_page_keeps_five() -> None:
    restaurants = [place(str(index), f"Place {index:02d}", rating=5 - index / 100, votes=index) for index in range(1, 23)]
    pool = candidate_pool(restaurants, _manifest(), _prefs(min_rating=0))
    assert len(pool) == POOL_LIMIT
    assert pool[-1].name == "Place 20"
    assert all(item.name != "Place 21" for item in pool)
    ranking = rank(pool)
    assert ranking.source == "fallback"
    assert ranking.summary == ""
    assert [card.restaurant.name for card in ranking.cards] == [f"Place {index:02d}" for index in range(1, 6)]


def test_extra_and_service_flags_do_not_change_membership() -> None:
    restaurants = [
        place("1", "Delivery", online_order=True, book_table=False),
        place("2", "Walk in", online_order=False, book_table=False),
    ]
    manifest = _manifest()
    without = candidate_pool(restaurants, manifest, _prefs(extra=""))
    with_extra = candidate_pool(restaurants, manifest, _prefs(extra="quiet family seating"))
    assert _names(without) == _names(with_extra) == ["Delivery", "Walk in"]


def test_template_sentence_uses_the_catalog_row() -> None:
    restaurant = place("1", "Jalsa", votes=775, cost_for_two=800, rating=4.1)
    assert template_explanation(restaurant) == (
        "Jalsa in Banashankari serves North Indian, Chinese, "
        "rated 4.1 from 775 votes, about ₹800 for two."
    )


def test_home_shows_edges_and_neighborhoods() -> None:
    restaurants = [
        place("1", "Jalsa", location="Banashankari"),
        place("2", "Other", location="Jayanagar"),
        place("3", "Blank", location=""),
    ]
    response, catalog = _get("/", restaurants, cost_p33=100, cost_p66=200)
    assert response.status_code == 200
    assert "Medium is ₹100–₹200 for two" in response.text
    select = response.text.split('id="location"', 1)[1].split("</select>", 1)[0]
    assert 'value="Bangalore"' in select
    assert 'value="Bengaluru"' in select
    assert 'value="Banashankari"' in select
    assert 'value="Jayanagar"' in select
    assert select.count('value=""') == 1
    assert "<datalist" not in response.text
    assert FALLBACK_NOTICE not in response.text
    assert catalog.reads == 0


def test_two_cards_keep_pool_order_and_the_fallback_notice() -> None:
    restaurants = [
        place("1", "Second", rating=4.2, votes=5, url=""),
        place("2", "First", rating=4.6, votes=1, url="https://example.test/first", online_order=False, book_table=False),
    ]
    response, _catalog = _submit(_form(), restaurants)
    assert response.status_code == 200
    assert _card_names(response.text) == ["First", "Second"]
    assert FALLBACK_NOTICE in response.text
    assert 'data-source="fallback"' in response.text
    assert 'class="summary"' not in response.text
    first, second = _cards(response.text)
    assert 'href="https://example.test/first"' in first
    assert "<a " not in second
    assert "Online order: no" in first
    assert "Table booking: no" in first
    assert "About ₹100 for two" in first
    assert template_explanation(restaurants[1]) in first
    positions = [first.index(marker) for marker in (
        'class="name"',
        'class="cuisines"',
        'class="rating"',
        'class="cost"',
        'class="neighborhood"',
        'class="online-order"',
        'class="book-table"',
        'class="explanation"',
    )]
    assert positions == sorted(positions)


def test_more_than_five_matches_show_the_first_five() -> None:
    restaurants = [place(str(index), f"Place {index}", rating=5 - index / 10) for index in range(6)]
    response, _catalog = _submit(_form(min_rating="0"), restaurants)
    assert _card_names(response.text) == [f"Place {index}" for index in range(5)]
    assert "Place 5" not in response.text


def test_unknown_location_and_an_over_tight_filter_render_the_empty_state() -> None:
    restaurants = [place("1", "Jalsa", rating=4.1)]
    unknown, catalog = _submit(_form(location="Mumbai", cuisine="Chinese"), restaurants)
    assert unknown.status_code == 200
    assert "No restaurants match" in unknown.text
    assert "location, budget, cuisine, and minimum rating" in unknown.text
    assert "Location: Mumbai" in unknown.text
    assert "Cuisine: Chinese" in unknown.text
    assert 'class="card"' not in unknown.text
    assert FALLBACK_NOTICE not in unknown.text
    assert catalog.reads == 1

    tight, _catalog = _submit(_form(min_rating="5"), restaurants)
    assert "No restaurants match" in tight.text
    assert "Location: bangalore" in tight.text
    assert "Cuisine: Chinese" in tight.text
    assert 'class="card"' not in tight.text


def test_extra_does_not_add_or_remove_a_restaurant() -> None:
    restaurants = [
        place("1", "Chinese room", cuisines=["Chinese"], online_order=False),
        place("2", "Italian room", cuisines=["Italian"], online_order=True),
    ]
    first, _catalog = _submit(_form(cuisine="Chinese", extra=""), restaurants)
    second, _catalog = _submit(_form(cuisine="Chinese", extra="I want Italian and quick service"), restaurants)
    assert _card_names(first.text) == _card_names(second.text) == ["Chinese room"]
    assert "Online order: no" in first.text
    assert "Table booking" in first.text


def test_a_blank_cuisine_is_accepted() -> None:
    restaurants = [
        place("1", "Listed", cuisines=["Chinese"]),
        place("2", "Unlisted", cuisines=[]),
    ]
    response, catalog = _submit(_form(cuisine=""), restaurants)
    assert response.status_code == 200
    assert _card_names(response.text) == ["Listed", "Unlisted"]
    assert catalog.reads == 1


def test_trimmed_cuisine_and_budget_words_are_accepted() -> None:
    low, low_catalog = _submit(_form(cuisine=" Chinese ", budget="Low"), [place("1", "Jalsa")])
    assert low.status_code == 200
    assert _card_names(low.text) == ["Jalsa"]
    assert 'value="Chinese"' in low.text
    assert low_catalog.reads == 1
    medium, _catalog = _submit(
        _form(cuisine="Chinese", budget="MEDIUM"),
        [place("1", "Jalsa", cost_for_two=150)],
    )
    assert _card_names(medium.text) == ["Jalsa"]


def test_invalid_fields_are_all_reported_and_do_not_read_restaurants() -> None:
    response, catalog = _submit(
        {
            "location": "",
            "budget": "nope",
            "cuisine": " ",
            "min_rating": "9",
            "extra": "x" * 201,
        },
        [place("1", "Jalsa")],
    )
    assert response.status_code == 400
    for message in (
        "Enter a location.",
        "Budget must be low, medium, or high.",
        "Minimum rating must be a number from 0 to 5.",
        "Extra preference must be at most 200 characters.",
    ):
        assert message in response.text
    assert "Enter a cuisine." not in response.text
    assert 'class="card"' not in response.text
    assert "No restaurants match" not in response.text
    assert catalog.reads == 0


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("location", "a" * 81, "Location must be at most 80 characters."),
        ("cuisine", "b" * 41, "Cuisine must be at most 40 characters."),
        ("min_rating", "-0.1", "Minimum rating must be a number from 0 to 5."),
        ("min_rating", "5.1", "Minimum rating must be a number from 0 to 5."),
        ("min_rating", "nope", "Minimum rating must be a number from 0 to 5."),
        ("extra", "e" * 201, "Extra preference must be at most 200 characters."),
    ],
)
def test_a_single_invalid_field_does_not_read_restaurants(field: str, value: str, message: str) -> None:
    response, catalog = _submit(_form(**{field: value}), [place("1", "Jalsa")])
    assert response.status_code == 400
    assert message in response.text
    assert catalog.reads == 0


def test_boundary_lengths_and_rating_ends_are_accepted() -> None:
    neighborhood = "n" * 80
    cuisine = "c" * 40
    restaurants = [place("1", "Edge", location=neighborhood, cuisines=[cuisine], rating=0)]
    low, catalog = _submit(
        _form(location=neighborhood, cuisine=cuisine, min_rating="0", extra="e" * 200),
        restaurants,
    )
    assert low.status_code == 200
    assert _card_names(low.text) == ["Edge"]
    assert catalog.reads == 1
    top, _catalog = _submit(_form(min_rating="5"), [place("1", "Top", rating=5)])
    assert _card_names(top.text) == ["Top"]


def test_a_recommendation_opens_no_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse_connection(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a recommendation opened a connection")

    def refuse_model(*_args: object, **_kwargs: object) -> dict:
        raise AssertionError("a recommendation called the model")

    monkeypatch.setattr(socket, "create_connection", refuse_connection)
    monkeypatch.setattr("app.ranker.post_chat", refuse_model)
    response, _catalog = _submit(_form(), [place("1", "Jalsa")])
    assert response.status_code == 200
    assert 'data-source="fallback"' in response.text
    assert "datasets" not in __import__("sys").modules


def test_catalog_text_is_escaped() -> None:
    response, _catalog = _submit(_form(), [place("1", "<b>Bold</b>")])
    assert "&lt;b&gt;Bold&lt;/b&gt;" in response.text
    assert "<b>Bold</b>" not in response.text


def test_load_catalog_and_health(tmp_path: Path) -> None:
    path = tmp_path / "catalog.sqlite"
    ingest([_source_row()], path)
    catalog = load_catalog(path)
    loaded = catalog.read_restaurants()
    assert loaded[0].name == "Jalsa"
    assert loaded[0].rating == 4.1
    assert loaded[0].cost_for_two == 800
    assert loaded[0].cuisines == ["North Indian", "Chinese"]
    assert loaded[0].online_order is True
    assert catalog.manifest.restaurant_count == 1
    assert catalog.manifest.cost_p33 == 800
    with TestClient(create_app(catalog)) as client:
        health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}


def test_startup_exits_for_a_missing_empty_or_unreadable_catalog(tmp_path: Path) -> None:
    missing = tmp_path / "missing.sqlite"
    with pytest.raises(SystemExit):
        load_catalog(missing)
    with pytest.raises(SystemExit):
        main(["--catalog", str(missing)])

    empty = tmp_path / "empty.sqlite"
    ingest([], empty)
    with pytest.raises(SystemExit):
        load_catalog(empty)

    garbage = tmp_path / "garbage.sqlite"
    garbage.write_text("not a database", encoding="utf-8")
    with pytest.raises(SystemExit):
        load_catalog(garbage)

    no_manifest = tmp_path / "bare.sqlite"
    connection = sqlite3.connect(no_manifest)
    connection.execute("CREATE TABLE restaurants (id TEXT)")
    connection.commit()
    connection.close()
    with pytest.raises(SystemExit):
        load_catalog(no_manifest)

    with pytest.raises(SystemExit):
        create_app(Catalog([], _manifest(restaurant_count=0)))


def test_a_running_process_keeps_the_catalog_it_opened(tmp_path: Path) -> None:
    path = tmp_path / "catalog.sqlite"
    ingest([_source_row(name="Jalsa")], path)
    catalog = load_catalog(path)
    with TestClient(create_app(catalog)) as client:
        ingest([_source_row(name="Replacement", address="Other Road")], path)
        response = client.post("/recommendations", data=_form(location="Banashankari", budget="low"))
    assert "Jalsa" in response.text
    assert "Replacement" not in response.text
    connection = sqlite3.connect(path)
    stored = connection.execute("SELECT name FROM restaurants").fetchone()
    connection.close()
    assert stored is not None
    assert stored[0] == "Replacement"


def _submit(
    data: dict[str, str],
    restaurants: list[Restaurant],
    **manifest: object,
) -> tuple[object, Catalog]:
    catalog = _catalog(restaurants, **manifest)
    with TestClient(create_app(catalog)) as client:
        response = client.post("/recommendations", data=data)
    return response, catalog


def _get(path: str, restaurants: list[Restaurant], **manifest: object) -> tuple[object, Catalog]:
    catalog = _catalog(restaurants, **manifest)
    with TestClient(create_app(catalog)) as client:
        response = client.get(path)
    return response, catalog


def _catalog(restaurants: list[Restaurant], **manifest: object) -> Catalog:
    return Catalog(restaurants, _manifest(**manifest))


def _manifest(**overrides: object) -> Manifest:
    values: dict[str, object] = {
        "dataset": "ManikaSaini/zomato-restaurant-recommendation",
        "built_at": "2026-11-18T00:00:00+00:00",
        "source_rows": 1,
        "restaurant_count": 1,
        "dropped_blank_identity": 0,
        "missing_rating": 0,
        "missing_cost": 0,
        "unparsed_rate_values": [],
        "cost_p33": 100,
        "cost_p66": 200,
    }
    values.update(overrides)
    return Manifest(**values)  # type: ignore[arg-type]


def _prefs(**overrides: object) -> Preferences:
    values: dict[str, object] = {
        "location": "bangalore",
        "budget": "low",
        "cuisine": "Chinese",
        "min_rating": 4.0,
        "extra": "",
    }
    values.update(overrides)
    return Preferences(**values)  # type: ignore[arg-type]


def _form(**overrides: str) -> dict[str, str]:
    payload = {
        "location": "bangalore",
        "budget": "low",
        "cuisine": "Chinese",
        "min_rating": "4",
        "extra": "",
    }
    payload.update(overrides)
    return payload


def _names(restaurants: list[Restaurant]) -> list[str]:
    return [item.name for item in restaurants]


def _cards(page: str) -> list[str]:
    return [block.split("</article>", 1)[0] for block in page.split('<article class="card">')[1:]]


def _card_names(page: str) -> list[str]:
    names = []
    for block in _cards(page):
        heading = block.split('<h2 class="name">', 1)[1].split("</h2>", 1)[0]
        names.append(heading.split(">", 1)[-1].split("<", 1)[0] if "<a " in heading else heading)
    return names


def place(identifier: str, name: str, **overrides: object) -> Restaurant:
    values: dict[str, object] = {
        "id": identifier,
        "name": name,
        "address": "12, Main Road",
        "location": "Banashankari",
        "listed_cities": ["Banashankari"],
        "cuisines": ["North Indian", "Chinese"],
        "cost_for_two": 100,
        "rating": 4.1,
        "votes": 10,
        "rest_types": ["Casual Dining"],
        "dishes_liked": ["Pasta"],
        "online_order": True,
        "book_table": True,
        "url": f"https://example.test/{identifier}",
        "review_excerpt": "Quiet dinner",
    }
    values.update(overrides)
    return Restaurant(**values)  # type: ignore[arg-type]


def _source_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "name": "Jalsa",
        "address": "12, Main Road",
        "location": "Banashankari",
        "listed_in(city)": "Banashankari",
        "cuisines": "North Indian, Chinese",
        "approx_cost(for two people)": "800",
        "rate": "4.1/5",
        "votes": 20,
        "rest_type": "Casual Dining",
        "dish_liked": "Pasta",
        "online_order": "Yes",
        "book_table": "Yes",
        "url": "https://example.test/jalsa",
        "reviews_list": "[('4', 'Quiet dinner')]",
    }
    row.update(overrides)
    return row
