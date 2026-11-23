"""Form, filters, and recommendations.

The ranker calls the model only after a non-empty filtered set, and only when
the model environment is set. Otherwise the page uses the template list.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from app.catalog import CATALOG_PATH, Catalog, load_catalog
from app.filters import candidate_pool, parse_preferences
from app.json_api import meta_payload, recommendation_payload
from app.pages import render_empty, render_home, render_invalid, render_results
from app.ranker import rank

_LOCAL_ORIGINS = ("http://127.0.0.1:3000", "http://localhost:3000")
_VERCEL_ORIGIN_REGEX = r"^https://.*\.vercel\.app$"


def cors_origins() -> list[str]:
    """Local dev origins, plus any comma-separated CORS_ORIGINS values."""
    origins = list(_LOCAL_ORIGINS)
    seen = set(origins)
    for item in os.environ.get("CORS_ORIGINS", "").split(","):
        origin = item.strip().rstrip("/")
        if not origin or origin in seen:
            continue
        seen.add(origin)
        origins.append(origin)
    return origins


def create_app(catalog: Catalog) -> FastAPI:
    """Serve the form. The process exits when the catalog has no restaurants."""
    if catalog.manifest.restaurant_count <= 0:
        raise SystemExit("catalog has no restaurants")
    app = FastAPI()
    app.state.catalog = catalog
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(),
        allow_origin_regex=_VERCEL_ORIGIN_REGEX,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def home() -> HTMLResponse:
        return HTMLResponse(render_home(catalog))

    @app.post("/recommendations", response_class=HTMLResponse)
    async def recommendations(request: Request) -> HTMLResponse:
        form = await _form_fields(request)
        preferences, errors = parse_preferences(form)
        if preferences is None:
            return HTMLResponse(render_invalid(catalog, form, errors), status_code=400)
        pool = candidate_pool(catalog.read_restaurants(), catalog.manifest, preferences)
        if not pool:
            return HTMLResponse(render_empty(catalog, preferences))
        return HTMLResponse(render_results(catalog, preferences, rank(pool, preferences)))

    @app.get("/api/meta")
    def api_meta() -> dict[str, object]:
        return meta_payload(catalog)

    @app.post("/api/recommendations")
    async def api_recommendations(request: Request) -> JSONResponse:
        try:
            payload = await request.json()
        except ValueError:
            payload = None
        body, status = recommendation_payload(catalog, payload)
        return JSONResponse(body, status_code=status)

    return app


async def _form_fields(request: Request) -> dict[str, str]:
    body = (await request.body()).decode("utf-8", errors="replace")
    parsed = parse_qs(body, keep_blank_values=True)
    return {key: values[-1] for key, values in parsed.items()}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Serve restaurant recommendations.")
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    # Railway injects PORT and reaches the container on 0.0.0.0. A local run keeps 127.0.0.1:8000.
    parser.add_argument("--host", default="0.0.0.0" if os.environ.get("PORT") else "127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    args = parser.parse_args(argv)
    catalog = load_catalog(args.catalog)
    import uvicorn

    uvicorn.run(create_app(catalog), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
