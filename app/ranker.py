"""Rank a filtered pool and explain each shown restaurant.

When LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL are set, this posts one
OpenAI-compatible chat completion and retries that call once. This project
calls Groq at https://api.groq.com/openai/v1. The same client can call any
other host that speaks that API. A missing setting or a second failure returns
the pool order with the template sentence, and does not open a connection
when the setting is missing.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from app.catalog import Restaurant
from app.filters import Preferences
from app.prompt import build_messages

PAGE_LIMIT = 5
FALLBACK_NOTICE = (
    "The list is ordered by rating and votes because a model ranking was not available."
)
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)

ChatTransport = Callable[[str, dict[str, str], dict, float], dict]


class ModelReplyError(Exception):
    """The completion could not be turned into the ranked-list schema."""


class RankedItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    explanation: str


class RankedBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    summary: str
    ranked: list[RankedItem]


@dataclass(frozen=True)
class LlmSettings:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: float


@dataclass(frozen=True)
class Card:
    restaurant: Restaurant
    explanation: str
    explanation_from: str


@dataclass(frozen=True)
class Ranking:
    source: str
    summary: str
    cards: list[Card]


def template_explanation(restaurant: Restaurant) -> str:
    """Fixed sentence. Every number in it comes from the catalog row."""
    rating = restaurant.rating
    cost = restaurant.cost_for_two
    if rating is None or cost is None:
        raise ValueError("a card requires a rating and a cost")
    cuisines = ", ".join(restaurant.cuisines)
    return (
        f"{restaurant.name} in {restaurant.location} serves {cuisines}, "
        f"rated {format(rating, 'g')} from {restaurant.votes} votes, "
        f"about ₹{cost} for two."
    )


def load_settings(environ: Mapping[str, str] | None = None) -> LlmSettings | None:
    """Read the model environment. A blank value counts as unset."""
    env = os.environ if environ is None else environ
    base_url = str(env.get("LLM_BASE_URL", "")).strip()
    api_key = str(env.get("LLM_API_KEY", "")).strip()
    model = str(env.get("LLM_MODEL", "")).strip()
    if not base_url or not api_key or not model:
        return None
    return LlmSettings(
        base_url=base_url.rstrip("/"),
        api_key=api_key,
        model=model,
        timeout_seconds=_timeout_seconds(env.get("LLM_TIMEOUT_SECONDS", "")),
    )


def rank(
    pool: list[Restaurant],
    preferences: Preferences | None = None,
    *,
    transport: ChatTransport | None = None,
    environ: Mapping[str, str] | None = None,
) -> Ranking:
    """Rank the pool. Unset model settings, or two failed calls, use the template."""
    if not pool or preferences is None:
        return fallback_ranking(pool)
    settings = load_settings(environ)
    if settings is None:
        return fallback_ranking(pool)
    sender = post_chat if transport is None else transport
    try:
        body = _complete(settings, build_messages(preferences, pool), sender)
    except ModelReplyError:
        return fallback_ranking(pool)
    return _merge(pool, body)


def fallback_ranking(pool: list[Restaurant]) -> Ranking:
    """Pool order, template sentences, and an empty summary."""
    shown = pool[:PAGE_LIMIT]
    return Ranking(
        source="fallback",
        summary="",
        cards=[
            Card(
                restaurant=item,
                explanation=template_explanation(item),
                explanation_from="template",
            )
            for item in shown
        ],
    )


def checked_explanation(text: str, restaurant: Restaurant) -> tuple[str, str]:
    """Keep a model sentence whose numbers all sit on the candidate. Otherwise the template."""
    cleaned = text.strip()
    if not cleaned or not _numbers_allowed(cleaned, restaurant):
        return template_explanation(restaurant), "template"
    return cleaned, "model"


def chat_payload(settings: LlmSettings, messages: list[dict[str, str]]) -> dict:
    """Chat-completions body. Groq gpt-oss also gets a short hidden reasoning pass."""
    payload: dict = {
        "model": settings.model,
        "temperature": 0,
        "messages": messages,
        "response_format": {"type": "json_object"},
        "max_completion_tokens": 4096,
    }
    if _groq_reasoning_model(settings):
        payload["reasoning_effort"] = "low"
        payload["reasoning_format"] = "hidden"
    return payload


def post_chat(url: str, headers: dict[str, str], payload: dict, timeout: float) -> dict:
    """POST one completion. HTTP failures propagate so the caller can retry once."""
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        try:
            body = response.json()
        except ValueError as exc:
            raise ModelReplyError("response is not JSON") from exc
    if not isinstance(body, dict):
        raise ModelReplyError("response is not an object")
    return body


def parse_completion(body: object) -> RankedBody:
    """Pull the JSON object out of an OpenAI-style completion and check the schema."""
    if not isinstance(body, dict):
        raise ModelReplyError("response is not an object")
    try:
        message = body["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ModelReplyError("missing completion message") from exc
    if not isinstance(message, dict):
        raise ModelReplyError("missing completion message")
    content = message.get("content")
    if content is None or (isinstance(content, str) and not content.strip()):
        content = message.get("reasoning")
    if isinstance(content, str):
        try:
            data = _load_json_object(content)
        except json.JSONDecodeError as exc:
            raise ModelReplyError("content is not JSON") from exc
    elif isinstance(content, dict):
        data = content
    else:
        raise ModelReplyError("content is not JSON")
    try:
        return RankedBody.model_validate(data)
    except ValidationError as exc:
        raise ModelReplyError("schema") from exc


def _complete(settings: LlmSettings, messages: list[dict[str, str]], transport: ChatTransport) -> RankedBody:
    url = f"{settings.base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }
    payload = chat_payload(settings, messages)
    last_error: Exception | None = None
    for _attempt in range(2):
        try:
            body = transport(url, headers, payload, settings.timeout_seconds)
            return parse_completion(body)
        except (ModelReplyError, httpx.HTTPError, json.JSONDecodeError) as exc:
            last_error = exc
    raise ModelReplyError("model call failed") from last_error


def _merge(pool: list[Restaurant], body: RankedBody) -> Ranking:
    by_id = {restaurant.id: restaurant for restaurant in pool}
    cards: list[Card] = []
    used: set[str] = set()
    for pick in body.ranked:
        restaurant = by_id.get(pick.id)
        if restaurant is None or pick.id in used:
            continue
        used.add(pick.id)
        explanation, origin = checked_explanation(pick.explanation, restaurant)
        cards.append(Card(restaurant, explanation, origin))
        if len(cards) == PAGE_LIMIT:
            break
    if len(cards) < PAGE_LIMIT:
        for restaurant in pool:
            if restaurant.id in used:
                continue
            cards.append(
                Card(restaurant, template_explanation(restaurant), "template")
            )
            if len(cards) == PAGE_LIMIT:
                break
    return Ranking(source="model", summary=body.summary, cards=cards)


def _numbers_allowed(text: str, restaurant: Restaurant) -> bool:
    rating = restaurant.rating
    cost = restaurant.cost_for_two
    if rating is None or cost is None:
        return False
    allowed_rating = f"{rating:.1f}"
    return all(
        _token_allowed(token, allowed_rating, restaurant.votes, cost)
        for token in _NUMBER.findall(text)
    )


def _token_allowed(token: str, allowed_rating: str, votes: int, cost: int) -> bool:
    if "." in token:
        fraction = token.split(".", 1)[1]
        return len(fraction) == 1 and token == allowed_rating
    value = int(token)
    if value == votes or value == cost:
        return True
    whole, _decimal = allowed_rating.split(".", 1)
    return allowed_rating.endswith(".0") and value == int(whole)


def _timeout_seconds(value: object) -> float:
    text = str(value).strip()
    if not text:
        return 20.0
    try:
        parsed = float(text)
    except ValueError:
        return 20.0
    if parsed <= 0:
        return 20.0
    return parsed


def _groq_reasoning_model(settings: LlmSettings) -> bool:
    return "groq.com" in settings.base_url.lower() and "gpt-oss" in settings.model.lower()


def _load_json_object(text: str) -> object:
    stripped = text.strip()
    fenced = _FENCE.match(stripped)
    if fenced:
        stripped = fenced.group(1).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(stripped[start : end + 1])
