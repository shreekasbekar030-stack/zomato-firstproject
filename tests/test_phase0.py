"""Phase 0 catalog ingest. Fixture rows only. The dataset is not downloaded."""

import json
import sqlite3
from pathlib import Path

import pytest

from app.ingest import (
    budget_edges,
    build_catalog,
    collapse,
    ingest,
    main,
    parse_cost,
    parse_excerpt,
    parse_listing,
    parse_rating,
    parse_votes,
    restaurant_id,
)


def test_rating_keeps_an_in_range_number_and_rejects_the_rest() -> None:
    assert parse_rating("4.1/5") == 4.1
    assert parse_rating("4.1 /5") == 4.1
    assert parse_rating("0") == 0
    assert parse_rating("5") == 5
    assert parse_rating("5.0") == 5.0
    assert parse_rating("NEW 4") == 4
    assert parse_rating("4 then 2") == 4
    assert parse_rating("NEW") is None
    assert parse_rating("-") is None
    assert parse_rating("") is None
    assert parse_rating(None) is None
    assert parse_rating("6") is None
    assert parse_rating("-1") is None


def test_cost_strips_commas_and_spaces_and_rejects_other_text() -> None:
    assert parse_cost("1,200") == 1200
    assert parse_cost("1,20,0") == 1200
    assert parse_cost(" 800 ") == 800
    assert parse_cost("0") == 0
    assert parse_cost("") is None
    assert parse_cost(None) is None
    assert parse_cost("800 rupees") is None
    assert parse_cost("1,200.50") is None


def test_votes_that_are_not_a_non_negative_integer_become_zero() -> None:
    assert parse_votes(None) == 0
    assert parse_votes(-3) == 0
    assert parse_votes("nope") == 0
    assert parse_votes("10.5") == 0
    assert parse_votes("775") == 775
    assert parse_votes(12) == 12


def test_excerpt_keeps_the_first_review_and_cuts_at_400() -> None:
    raw = "[('4', 'A  beautiful\\nplace'), ('3', 'ignored')]"
    assert parse_excerpt(raw) == "A beautiful place"
    long = "[('4', '" + ("word " * 200) + "')]"
    excerpt = parse_excerpt(long)
    assert len(excerpt) == 400
    assert parse_excerpt("[]") == ""
    assert parse_excerpt("[('4', '   ')]") == ""
    assert parse_excerpt("not a literal") == ""
    assert parse_excerpt(None) == ""


def test_tertiles_use_nearest_rank_and_skip_null_costs() -> None:
    assert budget_edges([300, 100, 200]) == (100, 200)
    assert budget_edges([450]) == (450, 450)
    assert budget_edges([]) == (None, None)


def test_collapse_keeps_higher_votes_and_unions_cuisines() -> None:
    rows = [
        _row(name="Jalsa", address="12, Main Road", votes=10, cuisines="North Indian, Chinese", rate="3.9", cost="500", reviews_list="[('3', 'older note')]"),
        _row(name="  jalsa ", address="12,   main road", votes=80, cuisines="Chinese, Mughlai", rate="4.2", cost="800", url="https://example.test/jalsa", location="Banashankari", reviews_list="[('4', 'winner note')]"),
    ]
    restaurants, manifest = build_catalog(rows)
    assert manifest["restaurant_count"] == 1
    assert manifest["dropped_blank_identity"] == 0
    restaurant = restaurants[0]
    assert restaurant["id"] == restaurant_id("Jalsa", "12, Main Road")
    assert restaurant["votes"] == 80
    assert restaurant["rating"] == 4.2
    assert restaurant["cost_for_two"] == 800
    assert restaurant["url"] == "https://example.test/jalsa"
    assert restaurant["location"] == "Banashankari"
    assert restaurant["cuisines"] == ["Chinese", "Mughlai", "North Indian"]
    assert restaurant["review_excerpt"] == "winner note"
    assert restaurant["name"] == "jalsa"


def test_ties_break_toward_rating_then_cost_then_earlier_row() -> None:
    null_rating = _row(votes=5, rate="NEW", cost="400", url="https://example.test/null")
    higher_rating = _row(votes=5, rate="4.5", cost=None, url="https://example.test/high")
    restaurants, _manifest = build_catalog([null_rating, higher_rating])
    assert restaurants[0]["url"] == "https://example.test/high"
    assert restaurants[0]["rating"] == 4.5

    with_cost = _row(votes=5, rate="4.0", cost="300", url="https://example.test/cost")
    without_cost = _row(votes=5, rate="4.0", cost=None, url="https://example.test/empty")
    chosen, _manifest = build_catalog([without_cost, with_cost])
    assert chosen[0]["url"] == "https://example.test/cost"

    first = _row(votes=5, rate="4.0", cost="300", url="https://example.test/first")
    second = _row(votes=5, rate="4.0", cost="300", url="https://example.test/second")
    stable, _manifest = build_catalog([first, second])
    assert stable[0]["url"] == "https://example.test/first"


def test_blank_identity_is_dropped_and_branches_stay_separate() -> None:
    rows = [
        _row(name="   ", address="Somewhere"),
        _row(name="Cafe", address="  "),
        _row(name="Cafe", address="One Road"),
        _row(name="Cafe", address="Other Road"),
        _row(name="Other", address="One Road"),
    ]
    restaurants, manifest = build_catalog(rows)
    assert manifest["dropped_blank_identity"] == 2
    assert manifest["source_rows"] == 5
    assert manifest["restaurant_count"] == 3
    assert len({item["id"] for item in restaurants}) == 3


def test_flags_locations_and_lists_follow_the_winner_rules() -> None:
    winner = _row(
        votes=2,
        online_order="no",
        book_table="No",
        location="",
        city="",
        cuisines="North Indian, , Chinese",
        rest_type="Cafe, Casual Dining",
        dish_liked="Pasta",
    )
    loser = _row(
        votes=1,
        online_order=" Yes ",
        book_table="true",
        location="Jayanagar",
        city="South Bangalore",
        cuisines="Chinese, BBQ",
        rest_type="Cafe",
        dish_liked="Biryani",
    )
    restaurants, _manifest = build_catalog([winner, loser])
    restaurant = restaurants[0]
    assert restaurant["online_order"] is True
    assert restaurant["book_table"] is False
    assert restaurant["location"] == ""
    assert restaurant["listed_cities"] == ["South Bangalore"]
    assert restaurant["cuisines"] == ["North Indian", "Chinese", "BBQ"]
    assert restaurant["rest_types"] == ["Cafe", "Casual Dining"]
    assert restaurant["dishes_liked"] == ["Pasta", "Biryani"]


def test_same_key_keeps_the_same_id() -> None:
    first = restaurant_id("Jalsa", "12, Main Road")
    second = restaurant_id("  JALSA", "12,   main road")
    assert first == second
    assert len(first) == 16
    assert first != restaurant_id("Jalsa", "12, Main Road,")


def test_fixture_ingest_writes_a_catalog_without_private_columns(tmp_path: Path) -> None:
    rows = [
        _row(name="Kept", address="Address", rate="4.1/5", cost="1,200", votes=10, phone="999", menu_item="secret", reviews_list="[('4', 'Nice place')]"),
        _row(name="kept", address="address", rate="NEW", cost=None, votes=1, cuisines="South Indian"),
        _row(name="Other", address="Elsewhere", rate="-", cost="", votes=3),
        _row(name="Blank", address="   ", rate="6"),
    ]
    output = tmp_path / "catalog.sqlite"
    manifest = ingest(rows, output)
    assert manifest["restaurant_count"] == 2
    assert manifest["dropped_blank_identity"] == 1
    assert manifest["missing_rating"] == 1
    assert manifest["missing_cost"] == 1
    assert manifest["unparsed_rate_values"] == ["NEW", "-", "6"]
    assert manifest["cost_p33"] == 1200
    assert manifest["cost_p66"] == 1200
    assert manifest["dataset"] == "ManikaSaini/zomato-restaurant-recommendation"
    assert not (tmp_path / "catalog.sqlite.tmp").exists()

    connection = sqlite3.connect(output)
    columns = [row[1] for row in connection.execute("PRAGMA table_info(restaurants)")]
    assert "phone" not in columns
    assert "menu_item" not in columns
    assert "reviews_list" not in columns
    indexes = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
    assert {"idx_restaurants_location", "idx_restaurants_rating", "idx_restaurants_cost"} <= indexes
    stored = connection.execute("SELECT name, votes, cuisines, review_excerpt, cost_for_two FROM restaurants WHERE name = 'Kept'").fetchone()
    assert stored[1] == 10
    assert json.loads(stored[2]) == ["North Indian", "Chinese", "South Indian"]
    assert stored[3] == "Nice place"
    assert stored[4] == 1200
    manifest_row = connection.execute("SELECT restaurant_count, unparsed_rate_values FROM manifest").fetchone()
    assert manifest_row[0] == 2
    assert json.loads(manifest_row[1]) == ["NEW", "-", "6"]
    connection.close()


def test_all_null_costs_leave_the_edges_null(tmp_path: Path) -> None:
    rows = [_row(rate="4.0", cost=None), _row(name="Two", address="Two Road", rate="NEW", cost="")]
    _restaurants, manifest = build_catalog(rows)
    assert manifest["cost_p33"] is None
    assert manifest["cost_p66"] is None
    assert manifest["missing_cost"] == 2
    assert manifest["missing_rating"] == 1
    assert manifest["unparsed_rate_values"] == ["NEW"]


def test_command_prints_the_manifest_and_replaces_the_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "rows.json"
    source.write_text(json.dumps([_row(rate="NEW"), _row(name="Two", address="Lane", rate="3.5")]), encoding="utf-8")
    output = tmp_path / "nested" / "catalog.sqlite"
    main(["--rows-file", str(source), "--output", str(output)])
    printed = json.loads(capsys.readouterr().out)
    assert printed["restaurant_count"] == 2
    assert printed["unparsed_rate_values"] == ["NEW"]
    assert output.is_file()


def test_a_failed_command_does_not_delete_an_existing_catalog(tmp_path: Path) -> None:
    output = tmp_path / "catalog.sqlite"
    ingest([_row()], output)
    original = output.read_bytes()
    with pytest.raises(SystemExit):
        main(["--rows-file", str(tmp_path / "missing.json"), "--output", str(output)])
    assert output.read_bytes() == original
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    with pytest.raises(SystemExit):
        main(["--rows-file", str(broken), "--output", str(output)])
    assert output.read_bytes() == original
    not_a_list = tmp_path / "object.json"
    not_a_list.write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit):
        main(["--rows-file", str(not_a_list), "--output", str(output)])
    assert output.read_bytes() == original


def test_a_blank_rate_is_recorded_once() -> None:
    rows = [
        _row(rate=""),
        _row(name="Two", address="Lane", rate="   "),
        _row(name="Three", address="Other Lane", rate="4.1/5"),
    ]
    _restaurants, manifest = build_catalog(rows)
    assert manifest["unparsed_rate_values"] == [""]
    assert manifest["missing_rating"] == 2


def test_zero_rows_write_an_empty_catalog(tmp_path: Path) -> None:
    manifest = ingest([], tmp_path / "catalog.sqlite")
    assert manifest["source_rows"] == 0
    assert manifest["restaurant_count"] == 0
    assert manifest["cost_p33"] is None


def test_collapse_helper_does_not_merge_different_names() -> None:
    listings = []
    for index, name in enumerate(("Alpha", "Beta")):
        listing, _raw, _parsed = parse_listing(_row(name=name, address="Same Road"), index)
        assert listing is not None
        listings.append(listing)
    assert len(collapse(listings)) == 2


def _row(**overrides: object) -> dict:
    row = {
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
        "phone": "080",
        "menu_item": "secret menu",
    }
    aliases = {
        "cost": "approx_cost(for two people)",
        "city": "listed_in(city)",
    }
    for key, value in overrides.items():
        row[aliases.get(key, key)] = value
    return row
