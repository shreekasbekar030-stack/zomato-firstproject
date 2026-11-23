"""Phase 2 model ranking. A fake transport stands in for Groq. No live key."""

import json
import socket

import httpx
import pytest
from fastapi.testclient import TestClient

from app.catalog import Catalog, Manifest, Restaurant
from app.filters import Preferences, candidate_pool
from app.main import create_app
from app.prompt import SYSTEM_INSTRUCTIONS, build_messages
from app.ranker import (
    FALLBACK_NOTICE,
    checked_explanation,
    parse_completion,
    rank,
    template_explanation,
)

GROQ_ENV = {
    "LLM_BASE_URL": "https://api.groq.com/openai/v1",
    "LLM_API_KEY": "test-key",
    "LLM_MODEL": "openai/gpt-oss-120b",
}


class ScriptedTransport:
    def __init__(self, results: list[object]) -> None:
        self.results = list(results)
        self.calls: list[dict[str, object]] = []

    def __call__(self, url: str, headers: dict[str, str], payload: dict, timeout: float) -> dict:
        self.calls.append({"url": url, "headers": headers, "payload": payload, "timeout": timeout})
        if not self.results:
            raise AssertionError("the model was called more than the script allows")
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result  # type: ignore[return-value]


def test_unset_or_partial_environment_does_not_connect(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse_connection(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a recommendation opened a connection")

    monkeypatch.setattr(socket, "create_connection", refuse_connection)
    restaurants = [_place("a", "First", rating=4.8, votes=3), _place("b", "Second", rating=4.2, votes=9)]
    transport = ScriptedTransport([])
    for environ in (
        {},
        {"LLM_BASE_URL": "https://api.groq.com/openai/v1"},
        {"LLM_BASE_URL": "https://api.groq.com/openai/v1", "LLM_API_KEY": "test-key"},
        {"LLM_BASE_URL": "  ", "LLM_API_KEY": "test-key", "LLM_MODEL": "openai/gpt-oss-120b"},
    ):
        ranking = rank(restaurants, _prefs(), transport=transport, environ=environ)
        assert ranking.source == "fallback"
        assert ranking.summary == ""
        assert [card.restaurant.name for card in ranking.cards] == ["First", "Second"]
        assert [card.explanation_from for card in ranking.cards] == ["template", "template"]
    assert transport.calls == []


def test_default_timeout_is_twenty_seconds_and_a_custom_timeout_is_sent() -> None:
    restaurants = [_place("a", "First")]
    default = ScriptedTransport([_completion("One place.", [{"id": "a", "explanation": "Rated 4.1 from 10 votes."}])])
    rank(restaurants, _prefs(), transport=default, environ=GROQ_ENV)
    assert default.calls[0]["timeout"] == 20.0

    custom = ScriptedTransport([_completion("", [{"id": "a", "explanation": "Rated 4.1 from 10 votes."}])])
    rank(
        restaurants,
        _prefs(),
        transport=custom,
        environ={**GROQ_ENV, "LLM_TIMEOUT_SECONDS": "12.5"},
    )
    assert custom.calls[0]["timeout"] == 12.5

    invalid = ScriptedTransport([_completion("", [{"id": "a", "explanation": "Rated 4.1 from 10 votes."}])])
    rank(
        restaurants,
        _prefs(),
        transport=invalid,
        environ={**GROQ_ENV, "LLM_TIMEOUT_SECONDS": "nope"},
    )
    assert invalid.calls[0]["timeout"] == 20.0


def test_groq_request_asks_for_a_json_object_and_short_reasoning() -> None:
    restaurants = [_place("a", "First", url="https://example.test/secret", address="12, Secret Road")]
    transport = ScriptedTransport([_completion("Summary.", [{"id": "a", "explanation": "Rated 4.1 from 10 votes."}])])
    rank(restaurants, _prefs(extra="quiet seating"), transport=transport, environ=GROQ_ENV)
    call = transport.calls[0]
    assert call["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer test-key"
    payload = call["payload"]
    assert payload["model"] == "openai/gpt-oss-120b"
    assert payload["temperature"] == 0
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["reasoning_effort"] == "low"
    assert payload["reasoning_format"] == "hidden"
    assert "test-key" not in json.dumps({key: value for key, value in payload.items() if key != "messages"})

    other = ScriptedTransport([_completion("", [{"id": "a", "explanation": "Rated 4.1 from 10 votes."}])])
    rank(
        restaurants,
        _prefs(),
        transport=other,
        environ={
            "LLM_BASE_URL": "https://example.test/v1",
            "LLM_API_KEY": "test-key",
            "LLM_MODEL": "other-model",
        },
    )
    assert "reasoning_effort" not in other.calls[0]["payload"]


def test_empty_result_and_invalid_form_do_not_connect(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = ScriptedTransport([])
    monkeypatch.setattr("app.ranker.post_chat", transport)
    for name, value in GROQ_ENV.items():
        monkeypatch.setenv(name, value)
    restaurants = [_place("a", "Jalsa", rating=4.1)]
    empty, catalog = _submit(_form(location="Mumbai"), restaurants)
    assert empty.status_code == 200
    assert "No restaurants match" in empty.text
    assert 'class="card"' not in empty.text
    assert catalog.reads == 1

    invalid, invalid_catalog = _submit(_form(min_rating="9"), restaurants)
    assert invalid.status_code == 400
    assert "Minimum rating must be a number from 0 to 5." in invalid.text
    assert 'class="card"' not in invalid.text
    assert invalid_catalog.reads == 0
    assert transport.calls == []


def test_timeout_http_error_and_invalid_json_retry_then_fall_back(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(500, request=request)
    failures = [
        httpx.TimeoutException("timed out"),
        httpx.HTTPStatusError("down", request=request, response=response),
        {"choices": [{"message": {"content": "not json"}}]},
        {"choices": [{"message": {"content": json.dumps({"summary": 1, "ranked": []})}}]},
    ]
    for failure in failures:
        transport = ScriptedTransport([failure, failure])
        ranking = rank(_places(2), _prefs(), transport=transport, environ=GROQ_ENV)
        assert len(transport.calls) == 2
        assert ranking.source == "fallback"
        assert ranking.summary == ""
        assert [card.restaurant.name for card in ranking.cards] == ["Place 0", "Place 1"]
        assert all(card.explanation_from == "template" for card in ranking.cards)

    page_transport = ScriptedTransport([httpx.ConnectError("down"), httpx.ConnectError("down")])
    page = _page(monkeypatch, page_transport, _places(1))
    assert page.status_code == 200
    assert FALLBACK_NOTICE in page.text
    assert 'data-source="fallback"' in page.text
    assert 'class="summary"' not in page.text
    assert len(page_transport.calls) == 2


def test_a_failed_first_call_uses_the_second_and_a_good_first_call_stops() -> None:
    restaurants = _places(1)
    recovered = ScriptedTransport(
        [
            httpx.TimeoutException("timed out"),
            _completion("Recovered.", [{"id": "p0", "explanation": "Rated 4.9 from 30 votes, about 100 for two."}]),
        ]
    )
    ranking = rank(restaurants, _prefs(), transport=recovered, environ=GROQ_ENV)
    assert len(recovered.calls) == 2
    assert ranking.source == "model"
    assert ranking.summary == "Recovered."
    assert ranking.cards[0].explanation_from == "model"
    assert ranking.cards[0].explanation.startswith("Rated 4.9")

    once = ScriptedTransport(
        [
            _completion("Once.", [{"id": "p0", "explanation": "Rated 4.9 from 30 votes."}]),
            _completion("Ignored.", [{"id": "p0", "explanation": "Rated 4.9 from 30 votes."}]),
        ]
    )
    ranking = rank(restaurants, _prefs(), transport=once, environ=GROQ_ENV)
    assert len(once.calls) == 1
    assert ranking.summary == "Once."


def test_unknown_and_duplicate_ids_are_dropped_and_the_page_fills_to_five() -> None:
    restaurants = _places(6)
    transport = ScriptedTransport(
        [
            _completion(
                "A short list.",
                [
                    {"id": "not-in-pool", "explanation": "Rated 4.9 from 30 votes."},
                    {"id": "p2", "explanation": _safe(restaurants[2])},
                    {"id": "p2", "explanation": "duplicate should be ignored, rated 1.0"},
                    {"id": "p0", "explanation": _safe(restaurants[0])},
                ],
            )
        ]
    )
    ranking = rank(restaurants, _prefs(), transport=transport, environ=GROQ_ENV)
    assert ranking.source == "model"
    assert [card.restaurant.id for card in ranking.cards] == ["p2", "p0", "p1", "p3", "p4"]
    assert ranking.cards[0].explanation_from == "model"
    assert ranking.cards[1].explanation_from == "model"
    assert ranking.cards[2].explanation_from == "template"
    assert all(card.restaurant.id != "not-in-pool" for card in ranking.cards)
    assert len(ranking.cards) == 5

    empty_ranked = ScriptedTransport([_completion("Nothing usable.", [])])
    filled = rank(restaurants, _prefs(), transport=empty_ranked, environ=GROQ_ENV)
    assert filled.source == "model"
    assert [card.restaurant.id for card in filled.cards] == ["p0", "p1", "p2", "p3", "p4"]
    assert all(card.explanation_from == "template" for card in filled.cards)


def test_more_than_five_ids_keep_model_order() -> None:
    restaurants = _places(6)
    order = ["p5", "p4", "p3", "p2", "p1", "p0"]
    transport = ScriptedTransport(
        [
            _completion(
                "",
                [
                    {"id": item_id, "explanation": _safe(restaurants[int(item_id[1:])])}
                    for item_id in order
                ],
            )
        ]
    )
    ranking = rank(restaurants, _prefs(), transport=transport, environ=GROQ_ENV)
    assert [card.restaurant.id for card in ranking.cards] == order[:5]
    ratings = [card.restaurant.rating for card in ranking.cards]
    assert ratings != sorted(ratings, reverse=True)


def test_a_wrong_cost_is_replaced_and_allowed_numbers_are_kept() -> None:
    restaurant = _place("a", "Cafe 17", rating=4.1, votes=775, cost_for_two=800)
    kept, origin = checked_explanation(
        "Rated 4.1 from 775 votes, about 800 for two.",
        restaurant,
    )
    assert origin == "model"
    assert kept.startswith("Rated 4.1")

    whole, whole_origin = checked_explanation("Rated 4 from 10 votes.", _place("b", "Even", rating=4.0, votes=10))
    assert whole_origin == "model"
    assert whole == "Rated 4 from 10 votes."

    replaced, replaced_origin = checked_explanation(
        "Rated 4.1/5 and costs 999 for two.",
        restaurant,
    )
    assert replaced_origin == "template"
    assert replaced == template_explanation(restaurant)

    named, named_origin = checked_explanation(
        "Cafe 17 is rated 4.1 from 775 votes, about 800 for two.",
        restaurant,
    )
    assert named_origin == "template"
    assert "999" not in named

    blank, blank_origin = checked_explanation("   ", restaurant)
    assert blank_origin == "template"
    assert blank == template_explanation(restaurant)


def test_card_facts_stay_on_the_catalog_row_and_the_summary_follows_the_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    restaurant = _place(
        "a",
        "Jalsa",
        rating=4.1,
        votes=775,
        cost_for_two=800,
        url="https://example.test/jalsa",
    )
    transport = ScriptedTransport(
        [
            _completion(
                "One strong match.",
                [{"id": "a", "explanation": "Spice Kitchen is rated 4.9 and costs 100."}],
            )
        ]
    )
    page = _page(monkeypatch, transport, [restaurant], _form(budget="high"))
    assert page.status_code == 200
    assert "One strong match." in page.text
    assert 'class="summary"' in page.text
    assert 'data-source="model"' in page.text
    assert FALLBACK_NOTICE not in page.text
    assert "Jalsa" in page.text
    assert "Spice Kitchen" not in page.text
    assert "About ₹800 for two" in page.text
    assert 'data-explanation-from="template"' in page.text
    assert template_explanation(restaurant) in page.text

    quiet = ScriptedTransport(
        [_completion("   ", [{"id": "a", "explanation": "Rated 4.1 from 775 votes, about 800 for two."}])]
    )
    quiet_page = _page(monkeypatch, quiet, [restaurant], _form(budget="high"))
    assert 'class="summary"' not in quiet_page.text
    assert 'data-explanation-from="model"' in quiet_page.text
    assert "Rated 4.1 from 775 votes, about 800 for two." in quiet_page.text


def test_prompt_carries_the_extra_preference_and_omits_url_and_address() -> None:
    kept = _place("a", "Kept", cuisines=["Chinese"], rest_types=[], dishes_liked=[], review_excerpt="")
    dropped = _place("b", "Dropped", cuisines=["Italian"])
    preferences = _prefs(cuisine="Chinese", extra="a quiet family room")
    messages = build_messages(preferences, [kept])
    assert "does not show that preference" in SYSTEM_INSTRUCTIONS
    assert "JSON" in SYSTEM_INSTRUCTIONS
    user = json.loads(messages[1]["content"])
    assert user["preferences"]["extra"] == "a quiet family room"
    assert user["preferences"]["cuisine"] == "Chinese"
    candidate = user["candidates"][0]
    assert set(candidate) == {
        "id",
        "name",
        "location",
        "cuisines",
        "costForTwo",
        "rating",
        "votes",
        "restTypes",
        "dishesLiked",
        "onlineOrder",
        "bookTable",
        "reviewExcerpt",
    }
    assert candidate["restTypes"] == []
    assert candidate["dishesLiked"] == []
    assert candidate["reviewExcerpt"] == ""
    assert "url" not in candidate
    assert "address" not in candidate
    assert kept.url not in messages[1]["content"]
    assert kept.address not in messages[1]["content"]

    manifest = _manifest()
    without = candidate_pool([kept, dropped], manifest, _prefs(cuisine="Chinese", extra=""))
    with_extra = candidate_pool([kept, dropped], manifest, preferences)
    assert [item.id for item in without] == [item.id for item in with_extra] == ["a"]
    transport = ScriptedTransport(
        [_completion("", [{"id": "a", "explanation": "Rated 4.1 from 10 votes, about 100 for two."}])]
    )
    ranking = rank(with_extra, preferences, transport=transport, environ=GROQ_ENV)
    sent = json.loads(transport.calls[0]["payload"]["messages"][1]["content"])
    assert sent["preferences"]["extra"] == "a quiet family room"
    assert [item["id"] for item in sent["candidates"]] == ["a"]
    assert [card.restaurant.name for card in ranking.cards] == ["Kept"]


def test_fenced_and_prefixed_json_still_parse() -> None:
    body = {"summary": "Ok.", "ranked": [{"id": "a", "explanation": "Rated 4.1 from 10 votes."}]}
    encoded = json.dumps(body)
    fenced = parse_completion({"choices": [{"message": {"content": f"```json\n{encoded}\n```"}}]})
    assert fenced.summary == "Ok."
    prefixed = parse_completion({"choices": [{"message": {"content": f"Here you go:\n{encoded}"}}]})
    assert prefixed.ranked[0].id == "a"
    reasoned = parse_completion({"choices": [{"message": {"content": None, "reasoning": encoded}}]})
    assert reasoned.summary == "Ok."


def _page(
    monkeypatch: pytest.MonkeyPatch,
    transport: ScriptedTransport,
    restaurants: list[Restaurant],
    data: dict[str, str] | None = None,
):
    monkeypatch.setattr("app.ranker.post_chat", transport)
    for name, value in GROQ_ENV.items():
        monkeypatch.setenv(name, value)
    catalog = Catalog(restaurants, _manifest())
    with TestClient(create_app(catalog)) as client:
        return client.post("/recommendations", data=_form() if data is None else data)


def _completion(summary: str, ranked: list[dict[str, str]]) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": json.dumps({"summary": summary, "ranked": ranked})}}]}


def _safe(restaurant: Restaurant) -> str:
    return f"Rated {restaurant.rating:.1f} from {restaurant.votes} votes, about {restaurant.cost_for_two} for two."


def _places(count: int) -> list[Restaurant]:
    return [
        _place(f"p{index}", f"Place {index}", rating=4.9 - index / 10, votes=30 - index)
        for index in range(count)
    ]


def _submit(data: dict[str, str], restaurants: list[Restaurant]):
    catalog = Catalog(restaurants, _manifest())
    with TestClient(create_app(catalog)) as client:
        response = client.post("/recommendations", data=data)
    return response, catalog


def _form(**overrides: str) -> dict[str, str]:
    payload = {
        "location": "bangalore",
        "budget": "low",
        "cuisine": "Chinese",
        "min_rating": "0",
        "extra": "",
    }
    payload.update(overrides)
    return payload


def _prefs(**overrides: object) -> Preferences:
    values: dict[str, object] = {
        "location": "bangalore",
        "budget": "low",
        "cuisine": "Chinese",
        "min_rating": 0.0,
        "extra": "",
    }
    values.update(overrides)
    return Preferences(**values)  # type: ignore[arg-type]


def _manifest() -> Manifest:
    return Manifest(
        dataset="fixture",
        built_at="2026-11-18T00:00:00+00:00",
        source_rows=1,
        restaurant_count=1,
        dropped_blank_identity=0,
        missing_rating=0,
        missing_cost=0,
        unparsed_rate_values=[],
        cost_p33=100,
        cost_p66=200,
    )


def _place(identifier: str, name: str, **overrides: object) -> Restaurant:
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
