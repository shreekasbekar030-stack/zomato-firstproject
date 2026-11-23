# Zomato — Phase-wise Implementation Plan

This plan is how the service in [architecture.md](architecture.md) gets built against the problem in [problemStatement.md](problemStatement.md).

Each phase ships on its own. A later phase starts only after the current phase’s exit criteria pass. Filters stay in front of the model in every phase. Card facts stay copied from the catalog. A missing or failed model call still returns the filtered restaurants with a sentence built from the row.

Durations are not estimated. A phase is done when its exit criteria pass.

Tests use small in-memory listings or a fixture SQLite file. They do not download the 574 MB dataset. The real Hugging Face load happens once, in Phase 3.

These rules hold in every phase:

- One card per restaurant. Collapse happens before any request is served.
- Location, budget, cuisine, and minimum rating are hard filters. The extra preference never adds or removes a restaurant.
- `online_order` and `book_table` are shown and, from Phase 2, sent to the model. They are not filters.
- Phone numbers and `menu_item` are not stored. Raw `reviews_list` is not stored and is not sent to the model.
- Budget rupees come from the catalog manifest (`cost_p33`, `cost_p66`). They are not hard-coded.
- The catalog file and API keys are not committed. `data/` and `.env` stay out of git.

## Phase 0 — Catalog ingest

**Outcome.** A command reads listing rows, parses them, collapses duplicates, computes budget edges, and writes `data/catalog.sqlite`. There is no server and no model.

### Work

1. **Project shell.** `requirements.txt` with FastAPI, uvicorn, pydantic, httpx, pytest, and the Hugging Face `datasets` library. `datasets` is an ingest dependency. `pytest.ini` puts `app` on the path. `.gitignore` covers `.venv/`, `__pycache__/`, `.pytest_cache/`, `data/`, and `.env`. `.env.example` lists `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, and `LLM_TIMEOUT_SECONDS` with empty values.
2. **Parsers** in `app/ingest.py`, each callable without a download:
   - Rating: the first number in the string when it is between 0 and 5 inclusive. `NEW`, `-`, and blank become null.
   - Cost: strip commas and spaces, parse an integer. Blank becomes null.
   - Cuisines, restaurant types, and liked dishes: split on commas, trim, drop empties.
   - `online_order` and `book_table`: true only for `Yes`, ignoring case.
   - Review excerpt: parse a Python literal of `(rating, text)` pairs, keep the first text, collapse whitespace, cut at 400 characters. A failed parse stores an empty excerpt and keeps the row.
3. **Collapse.** Key is casefolded name plus address, with internal whitespace collapsed. Blank name or blank address drops the row and increments `dropped_blank_identity`. The highest-vote listing wins rating, votes, cost, url, location, and excerpt. Ties break toward the higher rating, then toward a non-null cost. Cuisines, restaurant types, liked dishes, and listing cities are unions, winning row first. Restaurant id is the first 16 hex characters of the SHA-256 of the collapse key.
4. **Budget edges.** Nearest-rank 33rd and 66th percentiles of non-null `cost_for_two`. Restaurants with a null cost stay in the table and match no band later.
5. **SQLite writer.** Tables `restaurants` and `manifest` with the columns in the architecture, written in one transaction. The writer replaces `data/catalog.sqlite`. Manifest fields: dataset name, `built_at`, `source_rows`, `restaurant_count`, `dropped_blank_identity`, `missing_rating`, `missing_cost`, `unparsed_rate_values`, `cost_p33`, `cost_p66`.
6. **Command.** `python -m app.ingest` loads the `train` split of `ManikaSaini/zomato-restaurant-recommendation`. `python -m app.ingest --rows-file <path>` loads a local JSON list so tests and a smoke run stay offline. The command prints the manifest, including every distinct `rate` string that did not parse.

### Exit criteria

- Rating, cost, collapse, excerpt, and tertile tests pass on fixture rows.
- A fixture ingest writes a catalog that opens, with `restaurant_count` equal to the collapsed set and `unparsed_rate_values` listing the rejected strings.
- The SQLite file has no phone column, no menu column, and no raw review column.
- Two fixture rows for one name and address become one restaurant: scalars from the higher-vote row, cuisines unioned.
- The full Hugging Face download is not required for this phase to pass.

## Phase 1 — Filtered results with template reasons

**Outcome.** A person can open the form, submit location, budget, cuisine, and minimum rating, and see up to five restaurants that already satisfy those filters. Explanations are the template sentence. The model is not called.

### Work

1. **Catalog reader** in `app/catalog.py`. Load restaurants and the manifest. Expose the distinct `location` values for the form’s suggestions.
2. **Startup.** The process exits when `data/catalog.sqlite` is missing or the manifest has `restaurant_count` of zero. `GET /health` returns 200 when the catalog is open and that count is greater than zero.
3. **Filters** in `app/filters.py`.
   - `bangalore` and `bengaluru`, case-insensitive and trimmed, keep every restaurant.
   - Any other query keeps a restaurant whose `location` matches exactly, or else whose `listed_cities` contains the query. Address is not compared.
   - Budget uses the manifest edges: low at or under `cost_p33`, medium between the edges, high above `cost_p66`. A null cost matches no band.
   - Cuisine is a case-insensitive substring of the joined cuisine list. An empty cuisine list does not match.
   - Rating keeps `rating >= min_rating`. A null rating does not match.
4. **Pool.** Sort matches by rating descending, votes descending, name ascending. Keep 20. The page shows 5. Both limits shrink when fewer restaurants remain.
5. **Template explanation.** `{name} in {location} serves {cuisines}, rated {rating} from {votes} votes, about ₹{cost} for two.` Page `source` is `fallback`. The summary is empty. The page says the list is ordered by rating and votes because a model ranking was not available.
6. **HTTP and page.** FastAPI. `GET /` renders the form and the budget edges from the manifest (“Medium is ₹{cost_p33}–₹{cost_p66} for two”, with the stored integers). `POST /recommendations` accepts `location` (required, at most 80 characters), `budget` (`low`, `medium`, or `high`), `cuisine` (required, at most 40 characters), `min_rating` (0 to 5 inclusive), and `extra` (optional, at most 200 characters). An invalid field redisplays the form with the error and does not read the restaurant table. A valid form that matches nothing renders the empty state, names the filters, and echoes the location and cuisine. A card shows, in order: name linked with `url` when present, cuisines, rating and votes, cost for two, neighborhood, online order, table booking, explanation.

The ranker module in this phase is the template function only. It has no HTTP client.

### Exit criteria

- Fixture tests cover city-wide Bangalore, an exact neighborhood, an unknown location, cuisine substring, empty cuisines, null cost, band edges, and the rating floor.
- An unknown location and an over-tight filter render the empty state.
- A filtered set larger than five returns five cards, ordered by rating, then votes, then name. A set of two returns two cards.
- `extra`, `online_order`, and `book_table` do not change which restaurants appear. Online order and table booking still show on the card.
- An invalid form does not read restaurants.
- Cost on the card is labeled for two people.
- With no model code on the request path, a recommendation request opens no connection to an LLM host.
- The server process refuses to start when the catalog file is absent.

## Phase 2 — Model ranking and the explanation check

**Outcome.** When the three model variables are set, the model reorders the pool of at most 20 and writes reasons. Unknown ids are dropped. A reason whose numbers are not on the record is replaced with the template. When the variables are unset, or the call fails twice, the Phase 1 list is what the page shows.

### Work

1. **Prompt** in `app/prompt.py`. System instructions are the six rules in the architecture: rank only given ids, return JSON only, one or two sentences, numbers must be on the candidate, mention the extra preference only from `restTypes`, `dishesLiked`, or `reviewExcerpt`, and otherwise say the listing does not show it. The user message is the preferences plus the candidate array. Each candidate has `id`, `name`, `location`, `cuisines`, `costForTwo`, `rating`, `votes`, `restTypes`, `dishesLiked`, `onlineOrder`, `bookTable`, and `reviewExcerpt`. `url` and `address` are left out. Empty lists and an empty excerpt are sent as empty values.
2. **Client** in `app/ranker.py`. OpenAI-compatible `POST {LLM_BASE_URL}/chat/completions` via httpx. Bearer `LLM_API_KEY`. Model `LLM_MODEL`. Timeout `LLM_TIMEOUT_SECONDS`, default 20. `temperature` 0. Ask the host for a JSON object. If `LLM_BASE_URL`, `LLM_API_KEY`, or `LLM_MODEL` is unset, do not open a connection. Use the Phase 1 fallback.
3. **Schema.** The body must be `{ "summary": string, "ranked": [ { "id": string, "explanation": string } ] }`. A timeout, an HTTP error, or a body that fails the schema is tried once more. The second failure uses the fallback. `source` is `fallback` and the fallback notice is shown. `summary` is empty on that path.
4. **Merge.** Drop ids that are not in the pool. Drop duplicate ids, keeping the first. Fill any shortfall up to five from the pool’s original sort, skipping ids already used. Card fields other than the explanation are copied from the catalog.
5. **Number check.** Collect numbers in a model explanation. Each must equal that candidate’s rating (one decimal place), votes, or `costForTwo` (integers). A failed sentence is replaced with the template. The card records `explanationFrom` as `model` or `template`. When the call itself succeeded, page `source` stays `model`. A non-empty summary is shown only in that case.
6. **Wire-up.** `POST /recommendations` calls the ranker only after the filtered set is non-empty. Tests inject a fake transport. No test uses a real API key.

### Exit criteria

- With the model environment unset, `source` is `fallback`, the order is rating then votes then name, and no HTTP connection is opened.
- An empty filtered set does not open a connection.
- A response that names an id outside the pool does not create a card for it. The page still fills up to five from the pool.
- An explanation that cites a cost other than `costForTwo` is replaced by the template, and `explanationFrom` is `template`.
- A timeout, an HTTP error, or invalid JSON is attempted twice and then rendered as the fallback, with the fallback notice.
- A successful call shows the model order, the summary when present, and catalog facts on the card.
- The extra preference is present in the prompt and does not change pool membership.
- Phase 0 and Phase 1 tests still pass.

## Phase 3 — Real catalog and a full walkthrough

**Outcome.** The catalog is built from the Hugging Face dataset, and a person can run the form against that catalog in a browser. The manifest records the real row counts and the real rupee edges.

### Work

1. **Ingest the dataset.** Run `python -m app.ingest`. This downloads and parses the `train` split. It is expected to take a while and to use disk for the source file plus `data/catalog.sqlite`.
2. **Record the manifest.** Save the printed manifest to `docs/catalog-manifest.md`: dataset name, `built_at`, `source_rows`, `restaurant_count`, `dropped_blank_identity`, `missing_rating`, `missing_cost`, the list of unparsed `rate` strings, `cost_p33`, and `cost_p66`. These numbers are copied from that run. They are not chosen in advance. If a parser gap shows up in `unparsed_rate_values` that still contains a real score, fix the parser, re-run ingest, and replace the manifest note.
3. **Run the server** against `data/catalog.sqlite` with the model variables unset. Walk through in the browser:
   - The form shows the rupee edges from the manifest.
   - A Bangalore search with a budget band, a cuisine that exists in the data, and a minimum rating returns one to five cards. Each card shows name, cuisine, rating, cost labeled for two, and a template explanation. The fallback notice is visible.
   - A location that is not a neighborhood and not a listing area shows the empty state.
   - Submit an out-of-range minimum rating and confirm the form error, with no result list.
4. **Model path, when a key is available.** Set `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` in the environment, restart, and submit the same Bangalore search. Confirm either a model summary and reasons, or, if the host errors, the fallback notice and a list that still respects the filters. Do not put the key in the repo.
5. **Leave the key unset for the committed default.** `.env.example` stays empty of secrets. The server still answers with the fallback list.

### Exit criteria

- `docs/catalog-manifest.md` matches the ingest printout, `source_rows` is the dataset’s train size, and `restaurant_count` is smaller than `source_rows` because duplicate listings collapsed.
- `cost_p33` and `cost_p66` on the form match that manifest.
- The browser walkthrough above was done on the real catalog: a matching query, an unknown location, and an invalid rating.
- Automated tests from Phases 0–2 still pass without downloading the dataset.
- A recommendation card’s name, rating, and cost can be found on a row in `data/catalog.sqlite`.

## Phase 6 — Basic frontend

**Outcome.** The same form and cards are readable on a phone and a laptop. Nothing about filtering, ranking, or catalog facts changes.

### Work

1. **Restyle the existing page** in `app/pages.py`. No new framework, no new route, and no JSON API.
2. **Keep the contract.** The fields, budget sentence, datalist, card order, empty state, form errors, fallback notice, and model summary stay where the earlier phases put them.
3. **Layout.** A viewport tag, a single column on a narrow screen, and cards that stay in the required order: name, cuisines, rating and votes, cost for two, neighborhood, online order, table booking, explanation.

### Exit criteria

- Phase 0–2 tests still pass without a dataset download.
- In the browser, the form shows the manifest rupee edges, a matching search shows one to five cards, an unknown location shows the empty state, and an out-of-range rating shows the form error with no result list.

## What later work must not pull forward

- Phase 1 does not add an HTTP client. The fallback is the whole ranker until Phase 2.
- Phase 2 does not require a live key for its tests. The fake transport is the proof.
- Phase 3 does not change filter rules to make a query return more restaurants. An empty result stays empty.
- No phase adds live Zomato search, checkout, payments, delivery, or model training.
