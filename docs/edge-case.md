# Zomato — Edge Cases

This catalog is the expected behavior for boundary conditions in the restaurant recommender. It is derived from [architecture.md](architecture.md) and [implementation-plan.md](implementation-plan.md). A case that contradicts either document is a defect in this file. Update the source document first, then update the case.

Each case names the phase in which it becomes active. Until that phase ships, the behavior is not required. Cases marked **0** apply as soon as ingest exists. Cases marked **1** apply to the form and the template list. Cases marked **2** apply once the model client exists.

Fewer than five cards, an empty result, and a template sentence are valid outcomes. They are specified below so they are not repaired by relaxing a filter or by inventing a restaurant.

## Accepted limits

These are designed limits, not bugs.

| Limit | Behavior |
| --- | --- |
| Screen length | At most five cards. One, two, three, or four cards are a complete result. |
| Empty result | A valid form that matches nothing shows the empty state. The model is not called, and no restaurant from outside the filter is offered. |
| Pool cap | The model sees at most 20 matches. Match 21 and beyond, in rating / votes / name order, never reach the model and never appear on the page. |
| Equal tertiles | When `cost_p33` equals `cost_p66`, the medium band contains no cost. Costs at that value are low. Costs above it are high. |
| Cuisine match | The query is a case-insensitive substring of the joined cuisine list. A short query can match a longer cuisine word (`Bar` matches `Barbeque`). |
| City alias | Only `bangalore` and `bengaluru`, after trim and casefold, keep the whole catalog. `bangalore south` does not. |
| Address | Street text is stored and may be shown. It is not a filter and it is not sent to the model. |
| Collapse key | Normalization casefolds and collapses whitespace. It does not strip punctuation. `Road` and `Road,` stay two restaurants. |
| Explanation check | The server enforces candidate ids and numbers. It does not parse whether every cuisine word in the sentence is on the card. The prompt requires that. A sentence that fails the number check is replaced with the template. |
| Name that contains a number | The template may include that name. A model sentence that includes the same number is replaced with the template unless the number also equals the rating, the votes, or the cost. |
| Rating written as `4.1/5` | The `5` is a number. The sentence is replaced unless 5 equals that restaurant’s rating, votes, or cost. |
| Dropped columns | Phone, `menu_item`, and raw `reviews_list` are absent from SQLite on purpose. |
| Phase 1 ranker | The template function is the whole ranker. There is no HTTP client on the request path. |
| Tests | Phases 0–2 use fixture rows. They do not download the 574 MB dataset. |

## Ingest and identity

| ID | Situation | Expected behavior | Phase |
| --- | --- | --- | --- |
| IN-01 | Name is blank or only whitespace | The row is dropped. `dropped_blank_identity` increments by one. | 0 |
| IN-02 | Address is blank or only whitespace | The row is dropped. `dropped_blank_identity` increments by one. | 0 |
| IN-03 | Two rows differ only by letter case or internal whitespace in the name and the address | They collapse to one restaurant. | 0 |
| IN-04 | Same normalized name, different normalized address | Two restaurants. Branches stay separate. | 0 |
| IN-05 | Same normalized address, different normalized name | Two restaurants. | 0 |
| IN-06 | Two rows for one key, different vote counts | Scalars come from the higher-vote row: rating, votes, cost, url, location, review excerpt. | 0 |
| IN-07 | Votes tie, parsed ratings differ | The higher parsed rating wins the scalars. A null rating loses to any parsed rating. | 0 |
| IN-08 | Votes tie and ratings tie, one cost is null | The row with a non-null cost wins the scalars. | 0 |
| IN-09 | Votes, rating, and cost all tie | The earlier source row wins, so a second ingest of the same file produces the same ids and the same scalars. | 0 |
| IN-10 | Votes are missing on a row | Votes are 0 before the comparison. Any positive vote count beats it. | 0 |
| IN-11 | A losing row has a cuisine, restaurant type, liked dish, or listing city the winner lacks | That value is appended. The winner’s values stay first. Duplicate text is not repeated. | 0 |
| IN-12 | `online_order` or `book_table` is `Yes` on any row of the key, in any letter case, with surrounding whitespace | The restaurant’s flag is true. | 0 |
| IN-13 | Those fields are `No`, blank, `true`, or any other word | That row does not set the flag. The flag is still true if a different row of the same key is `Yes`. | 0 |
| IN-14 | The winner’s location is blank and a losing row has a neighborhood | Location stays blank. The losing row can still contribute its `listed_in(city)` to `listed_cities`. | 0 |
| IN-15 | The same collapse key is ingested twice | The id is the same 16 hex characters. It is the first 16 hex digits of the SHA-256 of the normalized key. | 0 |
| IN-16 | Ingest is run again | `data/catalog.sqlite` is replaced only after the new tables commit. A crash or a failed download leaves the previous file in place. | 0 |
| IN-17 | `--rows-file` points at a missing path | The command fails. It does not delete an existing catalog. | 0 |
| IN-18 | The input has zero rows | The command writes a catalog with `source_rows` 0 and `restaurant_count` 0. The server in Phase 1 then refuses to start. | 0 |
| IN-19 | Phone and `menu_item` are present on the source row | They are not written. The table has neither column. | 0 |
| IN-20 | `reviews_list` is present | Only `review_excerpt` is written. The raw column is absent. | 0 |

## Parsing

| ID | Situation | Expected behavior | Phase |
| --- | --- | --- | --- |
| PA-01 | `rate` is `4.1/5` or `4.1 /5` | Rating is 4.1. The string is not added to `unparsed_rate_values`. | 0 |
| PA-02 | `rate` is `0`, `5`, or `5.0` | Rating is 0, 5, or 5.0. The ends of the range are valid. | 0 |
| PA-03 | `rate` is `NEW`, `-`, or blank | Rating is null. The distinct raw string is stored on the manifest. | 0 |
| PA-04 | `rate` contains a number outside 0 to 5, such as `6` or `-1`, and no in-range number before it | Rating is null. The raw string is stored on the manifest. | 0 |
| PA-05 | `rate` contains more than one number | The first number is used when it is inside 0 to 5. Later numbers are ignored. | 0 |
| PA-06 | `rate` is `NEW 4` | The first number is 4, which is in range, so the rating is 4. The word `NEW` does not by itself force a null. | 0 |
| PA-07 | Cost is `1,200`, `1,20,0`, or ` 800 ` | Commas and spaces are removed, then the integer is parsed: 1200, 1200, and 800. | 0 |
| PA-08 | Cost is blank, `800 rupees`, `1,200.50`, or any other non-integer after the strip | Cost is null. The restaurant is still stored. | 0 |
| PA-09 | Cost is `0` | Cost is 0. It takes part in the tertiles and can match low. | 0 |
| PA-10 | Votes are missing, negative, or not an integer | Votes are 0. | 0 |
| PA-11 | Cuisine, restaurant type, or liked-dish text has empty pieces between commas | Empty pieces are dropped. Surrounding whitespace on a piece is removed. The stored words keep their original case. | 0 |

## Review excerpt

| ID | Situation | Expected behavior | Phase |
| --- | --- | --- | --- |
| RV-01 | `reviews_list` is a Python literal of `(rating, text)` pairs | The first pair’s text is kept. Whitespace collapses to single spaces. The excerpt is cut at 400 characters. | 0 |
| RV-02 | The first review is longer than 400 characters | The excerpt is 400 characters. The cut may fall inside a word. The rest is discarded. | 0 |
| RV-03 | The literal is an empty list, the first text is blank, or the value does not parse | The excerpt is empty. The restaurant stays in the catalog and can still match filters. | 0 |
| RV-04 | `reviews_list` is about a million characters | Ingest does not write that value. The prompt later receives at most the 400-character excerpt. | 0 |

## Budget bands

Percentile rank is 1-based nearest rank: `ceil(33/100 * N)` and `ceil(66/100 * N)` on the sorted non-null costs. `N` is the count of restaurants with a parsed cost.

| ID | Situation | Expected behavior | Phase |
| --- | --- | --- | --- |
| BD-01 | Costs are 100, 200, and 300 | `cost_p33` is 100. `cost_p66` is 200. Low is 100. Medium is 200. High is 300. | 0 |
| BD-02 | A cost equals `cost_p33` | It matches low. It does not match medium. | 1 |
| BD-03 | A cost equals `cost_p66` | It matches medium. It does not match high. | 1 |
| BD-04 | A cost is one rupee above `cost_p66` | It matches high. | 1 |
| BD-05 | `cost_p33` equals `cost_p66` | Medium matches nothing. A cost equal to that edge matches low. A higher cost matches high. | 1 |
| BD-06 | One restaurant has a cost, and it is the only parsed cost | Both edges equal that cost. It matches low. Medium and high match nothing. | 0 |
| BD-07 | Every cost is null | The edges are null. The restaurants are stored. Every budget selection matches nothing. No rupee value is invented. | 0 |
| BD-08 | A restaurant’s cost is null | It is excluded from the percentile input and it matches no band. | 0 |
| BD-09 | The form labels the bands | The label uses the integers on the manifest. The example in the architecture is only an illustration. | 1 |

## Location

Comparison is trim, then casefold. The city-wide check runs before the neighborhood check. The neighborhood check runs before `listed_cities`.

| ID | Situation | Expected behavior | Phase |
| --- | --- | --- | --- |
| LO-01 | Query is `bangalore`, `BANGALORE`, ` bangalore `, `bengaluru`, or `Bengaluru` | Every restaurant is kept, including restaurants whose neighborhood is blank. | 1 |
| LO-02 | Query is `bangalore south` or `greater bangalore` | This is not the city alias. It matches only an exact neighborhood or an exact listing city. | 1 |
| LO-03 | Query casefolds to a restaurant’s `location` | That restaurant is kept. Restaurants that merely list the same string in `listed_cities`, with a different neighborhood, are not kept. | 1 |
| LO-04 | Query matches no `location`, and it equals one entry in `listed_cities` | Restaurants with that listing city are kept. | 1 |
| LO-05 | Query is a prefix or a substring of a neighborhood, such as `Banas` for `Banashankari` | Empty set. Neighborhood match is exact. | 1 |
| LO-06 | Query is a street word that appears only in `address` | Empty set. The model is not called. | 1 |
| LO-07 | Query matches nothing | Empty state. The page names the filters and echoes the location and the cuisine. | 1 |
| LO-08 | A restaurant’s `location` is blank, and the query is a neighborhood | That restaurant is not kept, unless the query exactly equals one of its `listed_cities`. | 1 |
| LO-09 | The person asks for a city this dataset does not contain, such as Mumbai | Empty set. The catalog stays the Bangalore listings. | 1 |

## Cuisine and rating

| ID | Situation | Expected behavior | Phase |
| --- | --- | --- | --- |
| CU-01 | Cuisine is `chinese` and the list contains `Chinese` | The restaurant matches. | 1 |
| CU-02 | Cuisine is `Indian` and the list contains `North Indian` | The restaurant matches. | 1 |
| CU-03 | The cuisine list is empty | The restaurant matches no cuisine query. | 1 |
| CU-04 | Cuisine is ` Chinese ` | Trim, then apply CU-01. The stored pieces are not required to contain the spaces. | 1 |
| CU-05 | Cuisine is 40 characters and non-blank after trim | The form accepts it. | 1 |
| CU-06 | Cuisine is 41 characters, or blank after trim | The form shows the error. Restaurants are not read. The model is not called. | 1 |
| RT-01 | `min_rating` equals the restaurant’s rating | The restaurant is kept. The comparison is greater than or equal. | 1 |
| RT-02 | `min_rating` is 0 | Every restaurant with a parsed rating is kept, including a rating of 0. Null ratings are still excluded. | 1 |
| RT-03 | `min_rating` is 5 | Only restaurants rated 5 or above are kept. | 1 |
| RT-04 | The rating is null | The restaurant is excluded for every minimum, including 0. | 1 |
| RT-05 | `min_rating` is below 0, above 5, or not a number | The form shows the error. Restaurants are not read. | 1 |
| RT-06 | `min_rating` is 0 or 5 exactly | The form accepts it. | 1 |

## Form

| ID | Situation | Expected behavior | Phase |
| --- | --- | --- | --- |
| FM-01 | Location, budget, cuisine, or minimum rating is missing | The form shows the error. Restaurants are not read. The model is not called. | 1 |
| FM-02 | Several fields are invalid at once | Every invalid field is reported. Restaurants are still not read. | 1 |
| FM-03 | Location is 80 characters after trim | The form accepts it and runs the location rules. | 1 |
| FM-04 | Location is 81 characters, or blank after trim | The form shows the error. Restaurants are not read. | 1 |
| FM-05 | Budget is `Low`, `MEDIUM`, or `high` | Trim and casefold. The three bands are accepted. Any other word is a form error, and restaurants are not read. | 1 |
| FM-06 | `extra` is omitted or blank after trim | There is no extra preference. | 1 |
| FM-07 | `extra` is 200 characters | The form accepts it. In Phase 1 it does not change the result set. In Phase 2 it is included in the prompt. | 1 |
| FM-08 | `extra` is 201 characters | The form shows the error. Restaurants are not read. | 1 |
| FM-09 | `GET /` | The form renders with the manifest’s rupee edges and the distinct neighborhoods. The model is not called. | 1 |
| FM-10 | The person submits the form again from the result page | The fields show what they submitted, and the filters run again. | 1 |

## Pool and result page

Sort is rating descending, then votes descending, then name ascending by the stored name, then id ascending.

| ID | Situation | Expected behavior | Phase |
| --- | --- | --- | --- |
| PL-01 | The filtered set has 1, 2, 3, or 4 restaurants | The page shows that many cards. It does not pad. | 1 |
| PL-02 | The filtered set has 5 restaurants | The page shows all five. | 1 |
| PL-03 | The filtered set has 6 to 20 restaurants | The pool is the whole set. The page shows the first five of the sort. | 1 |
| PL-04 | The filtered set has 21 or more restaurants | The pool is the first 20 of the sort. The page shows the first five. Restaurant 21 is absent from the prompt and from the page. | 1 |
| PL-05 | Two restaurants share a rating and a vote count | The one whose stored name sorts earlier comes first. If the names are equal, the smaller id comes first. | 1 |
| PL-06 | The filtered set is empty | The empty state names the filters and echoes the submitted location and cuisine. No card is shown. | 1 |
| PL-07 | `extra` mentions a preference the winner does not support | The set is unchanged. Phase 1 still uses the template sentence. | 1 |
| PL-08 | `online_order` is false, or `book_table` is false | The restaurant can still appear. The card shows no for that flag. | 1 |
| PL-09 | `url` is empty | The name is text, not a link. The other card lines still render. | 1 |
| PL-10 | `url` is non-empty | The name links to that url. | 1 |
| PL-11 | A card renders | The order is name, cuisines, rating and votes, cost for two, neighborhood, online order, table booking, explanation. Cost is labeled for two people. | 1 |
| PL-12 | Phase 1 serves a non-empty list | `source` is `fallback`. The summary is empty. The page says the list is ordered by rating and votes because a model ranking was not available. The explanation is the template sentence. | 1 |
| PL-13 | A recommendation request in Phase 1 | No connection is opened to an LLM host. | 1 |

The template sentence is: `{name} in {location} serves {cuisines}, rated {rating} from {votes} votes, about ₹{cost} for two.`

## Model

Phase 2 only. A call is one HTTP request. A retry is a second request. There is no third request.

| ID | Situation | Expected behavior | Phase |
| --- | --- | --- | --- |
| MD-01 | `LLM_BASE_URL`, `LLM_API_KEY`, or `LLM_MODEL` is unset or blank | No connection is opened. The Phase 1 list is served, including the fallback notice. | 2 |
| MD-02 | Only one or two of those three variables are set | Same as MD-01. | 2 |
| MD-03 | `LLM_TIMEOUT_SECONDS` is unset | The timeout is 20 seconds. | 2 |
| MD-04 | The filtered set is empty | No connection is opened, including when the three variables are set. | 2 |
| MD-05 | The form is invalid | No connection is opened, and restaurants are not read. | 2 |
| MD-06 | The first call times out, returns an HTTP error, or returns a body that is not the schema | The client tries once more. | 2 |
| MD-07 | The second call also times out, errors, or fails the schema | `source` is `fallback`. The summary is empty. The fallback notice is shown. The order is the pool sort. | 2 |
| MD-08 | The first call fails and the second call returns valid JSON | `source` is `model`. The second body is used. There is no further call. | 2 |
| MD-09 | The first call returns valid JSON | There is no retry. | 2 |
| MD-10 | The model names an id that is not in the pool | That id does not become a card. The page does not fetch it from the rest of the catalog. | 2 |
| MD-11 | The same pool id appears twice in `ranked` | The first copy is kept, with its explanation. The later copy is ignored. | 2 |
| MD-12 | Every returned id is unknown, or `ranked` is empty | The page fills up to five cards from the pool sort. `source` stays `model` because the call succeeded. Filled cards use the template, with `explanationFrom` `template`. | 2 |
| MD-13 | The model returns one valid id and the pool has five or more | That id is first. The next four cards are the earliest pool-sort restaurants not already used. The page shows five. | 2 |
| MD-14 | The model returns more than five valid ids | The page shows the first five of that order. It does not re-sort those five by rating. | 2 |
| MD-15 | The model writes a different name, rating, or cost in the prose | The card’s facts stay the catalog values. | 2 |
| MD-16 | An explanation’s numbers each equal the rating at one decimal place, the vote count, or `costForTwo` | The sentence is kept. `explanationFrom` is `model`. | 2 |
| MD-17 | An explanation contains any other number, including a `5` from `4.1/5` or a number taken from the restaurant’s name | The sentence is replaced with the template. `explanationFrom` is `template`. `source` stays `model`. | 2 |
| MD-18 | The explanation is empty or only whitespace | It is replaced with the template. `explanationFrom` is `template`. | 2 |
| MD-19 | `summary` is a non-empty string and `source` is `model` | The summary is shown above the cards. | 2 |
| MD-20 | `summary` is empty, or `source` is `fallback` | No summary is shown. The fallback path also shows the fallback notice. | 2 |
| MD-21 | The extra preference is not supported by `restTypes`, `dishesLiked`, or `reviewExcerpt` | Membership is unchanged. The prompt tells the model to say the listing does not show that preference. A sentence that still uses only allowed numbers is kept. | 2 |
| MD-22 | `reviewExcerpt`, `dishesLiked`, or `restTypes` is empty | The prompt sends an empty string or an empty list. The restaurant remains eligible. | 2 |
| MD-23 | The candidate payload is built | `url` and `address` are absent. The id in the payload is the catalog id. | 2 |
| MD-24 | Tests exercise MD-06 through MD-18 | They use a fake transport. They do not read a real API key and they do not call a live host. | 2 |

The response schema is `{ "summary": string, "ranked": [ { "id": string, "explanation": string } ] }`. A missing field, a non-string summary, or a ranked entry that is not that pair fails the schema and follows MD-06.

## Startup and catalog use

| ID | Situation | Expected behavior | Phase |
| --- | --- | --- | --- |
| ST-01 | `data/catalog.sqlite` is missing | The process exits. `GET /health` is not served. | 1 |
| ST-02 | The file exists and the manifest is missing, or the file does not open | The process exits. | 1 |
| ST-03 | `restaurant_count` is 0 | The process exits. | 1 |
| ST-04 | The catalog opens and `restaurant_count` is greater than 0 | `GET /health` returns 200. | 1 |
| ST-05 | Ingest replaces the file while the server is running | The running process keeps the catalog it opened. The new file is what a restarted process reads. | 1 |
| ST-06 | A request is served | The request does not download the dataset and does not write the catalog. | 1 |

## Phase fences

| ID | Situation | Expected behavior | Phase |
| --- | --- | --- | --- |
| PH-01 | Phase 0 is under test | There is no recommendation route and no model client. Fixture rows are enough. | 0 |
| PH-02 | Phase 1 is under test | A recommendation request cannot open an LLM connection, because the client is not on the path. | 1 |
| PH-03 | Phase 2 is under test | A live key is not required. The fake transport is the proof for success, retry, and rejection. | 2 |
| PH-04 | The real dataset is loaded | `source_rows` is the train split size. `restaurant_count` is smaller, because duplicate listings collapsed. Both numbers are copied from that run into `docs/catalog-manifest.md`. | 3 |
| PH-05 | An unparsed `rate` string still contains a score a person would read as a rating | Fix the parser, run ingest again, and replace the manifest note. Do not type a rating into the manifest by hand. | 3 |
| PH-06 | A real query matches nothing | The empty state stays. Filters are not widened to fill the five cards. | 3 |
| PH-07 | A card is shown from the real catalog | That card’s name, rating, and cost occur on a row in `data/catalog.sqlite`. | 3 |
| PH-08 | A key was used for a manual model check | The key stays in the environment. `.env.example` has empty values. `.env` is not committed. | 3 |
| PH-09 | A change adds live Zomato search, checkout, payments, delivery, or model training | That change is outside this catalog and outside the plan. | 3 |
