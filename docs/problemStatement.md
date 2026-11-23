# Zomato — Project Context

This document is the source of context for the project. Later work — data loading, filtering, prompting, ranking, and the result screen — should stay consistent with it. If a decision here changes, update this file first.

## Project

Build an AI-powered restaurant recommendation service inspired by Zomato. The service suggests restaurants from a real restaurant dataset by combining structured filters with a large language model. The person states what they want. The system narrows the dataset to restaurants that fit, asks the model to rank that short set and explain each pick, and shows the result in a form they can act on.

The problem this solves: a person who wants to eat out has a location, a budget, a cuisine, and a minimum rating in mind, and sometimes an extra preference such as family-friendly or quick service. Scanning tens of thousands of listings to find a few that fit is the work the product takes on.

## Objective

Design and implement an application that:

1. Takes user preferences: location, budget, cuisine, minimum rating, and any extra preferences.
2. Uses a real-world dataset of restaurants.
3. Uses a large language model to produce personalized recommendations in plain language.
4. Displays clear, useful results.

## Who it is for

Someone choosing a restaurant. They know the area they will eat in, roughly what they want to spend, the kind of food, and how highly the place should be rated. They may also name something the listing should support, such as a family meal or quick service.

The unit of recommendation is a restaurant, with its name, cuisines, rating, and approximate cost. The product recommends places to go, drawn from the dataset below.

## Dataset

Source: [ManikaSaini/zomato-restaurant-recommendation](https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation) on Hugging Face.

Verified from the dataset viewer on 18 Nov 2026:

| Fact | Value |
| --- | --- |
| Split | `train` only |
| Rows | 51,717 |
| File size | 574 MB |
| Geography in the sample | Bangalore listings (neighborhoods such as Banashankari, Basavanagudi, Mysore Road) |
| Dataset card | None published |

Columns:

| Column | What it holds | Notes from the viewer |
| --- | --- | --- |
| `url` | Zomato page URL | String |
| `address` | Street address | String |
| `name` | Restaurant name | String |
| `online_order` | Whether online order is offered | Two classes, sample values `Yes` / `No` |
| `book_table` | Whether a table can be booked | Two classes, sample values `Yes` / `No` |
| `rate` | Rating | String, 64 distinct values, sample `4.1/5` |
| `votes` | Vote count | Integer, observed range 0 to 16,800 |
| `phone` | Phone numbers | String, can be null |
| `location` | Neighborhood | String, 93 distinct values |
| `rest_type` | Restaurant type | String, 93 distinct values, sample `Casual Dining`, `Cafe`, `Quick Bites` |
| `dish_liked` | Dishes people liked | String, can be null |
| `cuisines` | Cuisine list | String, can be null, sample `North Indian, Mughlai, Chinese` |
| `approx_cost(for two people)` | Approximate cost for two | String, 70 distinct values, sample `800` |
| `reviews_list` | Stored reviews | String, can be very long (up to about 1.28M characters) |
| `menu_item` | Menu items | String, often empty in the sample (`[]`) |
| `listed_in(type)` | Listing category | String, 7 distinct values, sample `Buffet`, `Cafes` |
| `listed_in(city)` | Listing city area | String, 30 distinct values |

The same restaurant can appear on more than one row. In the viewer sample, San Churro Cafe is listed once under `Buffet` and again under `Cafes`, with the same address and rating. A recommendation refers to the restaurant. [architecture.md](architecture.md) collapses rows on normalized name plus address.

Fields the assignment asks the screen to show, and where they come from:

| Shown to the user | Dataset field |
| --- | --- |
| Restaurant name | `name` |
| Cuisine | `cuisines` |
| Rating | `rate` |
| Estimated cost | `approx_cost(for two people)` |
| Why this place fits | Written by the model from the filtered row and the stated preferences |

`rate` is stored as text (`4.1/5`), and cost is stored as text. Both have to be parsed before a numeric filter can run. Rows with a missing cuisine, an unparseable rating, or an unparseable cost cannot honestly satisfy a filter on that field.

`reviews_list` is large enough that sending raw reviews for thousands of rows into a model call is not viable. The model should see a prepared slice: the restaurants that already passed the filters, with the fields needed to rank and explain.

## Workflow

1. **Data ingestion.** Load the Hugging Face dataset and preprocess it. Keep restaurant name, location, cuisine, cost, rating, and the other fields a filter or an explanation needs. Parse rating and cost into numbers. Record how duplicate rows and missing values are handled.
2. **User input.** Collect:
   - Location, for example Bangalore or a neighborhood such as Banashankari.
   - Budget: low, medium, or high.
   - Cuisine, for example Italian or Chinese.
   - Minimum rating.
   - Any additional preferences, for example family-friendly or quick service.
3. **Integration.** Filter the table to restaurants that match the stated location, budget, cuisine, and minimum rating. Prepare that structured result for the model. The prompt should give the model the filtered rows and the preferences, and ask it to reason about rank.
4. **Recommendation.** The model ranks the filtered restaurants, explains why each one fits the preferences, and may add a short summary of the set.
5. **Display.** Present the top recommendations with restaurant name, cuisine, rating, estimated cost, and the model’s explanation.

## What the model is for

The model ranks and explains restaurants that the filter has already kept. It writes the reason a place fits the stated preferences, and it may summarize the set.

An explanation has to be checkable against the row and the preferences that were passed in. A claim about cost, rating, cuisine, location, online order, table booking, restaurant type, or liked dishes has to come from those fields. A preference the dataset cannot support (the assignment’s examples are family-friendly and quick service) may be matched only through a field that actually speaks to it, such as `rest_type`, `dish_liked`, or review text that was included in the prompt. If nothing in the passed row supports the preference, the explanation says so.

## Output

Each recommendation shows:

- Restaurant name
- Cuisine
- Rating
- Estimated cost
- AI-generated explanation

The screen shows five recommendations. It shows fewer when the filtered set is smaller. The model sees at most 20 candidates. Both limits are specified in [architecture.md](architecture.md).

## Scope

In scope:

- Loading and preprocessing this dataset.
- A way to enter location, budget band, cuisine, minimum rating, and extra preferences.
- Filtering on those structured preferences.
- A prompt that asks the model to rank the filtered rows and explain each pick.
- A result view with the five fields above.

Outside this project:

- Live Zomato search, menus, cart, checkout, payments, or delivery assignment. This dataset is a static Bangalore dump, and `menu_item` is often empty.
- Training a new model. The model is called to rank and explain a prepared list.
- Cities that are not in this dataset. The listings are Bangalore.

## Data constraints later work has to respect

- Cost in the file is an approximate cost **for two people**, not a per-person price and not a delivery-cart total.
- Budget bands are the words low, medium, and high. Rupee edges are the 33rd and 66th percentiles of parsed cost-for-two, computed when the catalog is built and stored on the catalog manifest. The form shows those edges. The numeric cutoffs are not copied into this file because they come from the dataset at ingest time.
- Rating text is not a float until it is parsed. The column has 64 distinct strings, so the parser has to accept more than the `4.1/5` sample.
- Cuisine is a comma-separated list. A request for one cuisine should match a restaurant that serves that cuisine among others.
- Location in the file is a neighborhood (`location`, 93 values) and a listing area (`listed_in(city)`, 30 values). The assignment’s example input is “Bangalore”, which is the city these rows belong to, not one of the 93 neighborhoods. A city-level request and a neighborhood-level request are different filters.
- Nulls occur. `dish_liked`, `cuisines`, and `phone` are nullable in the viewer. A null cuisine cannot be shown as a cuisine match.
- One restaurant, many rows. Collapsing duplicates changes which rating, cost, and cuisine string win. That choice belongs in preprocessing and should be visible in the result (one card per restaurant).

## Decisions

[architecture.md](architecture.md) settles the questions that were open in the brief. The short form is here so this file stays the single context.

1. The screen shows five restaurants, fewer when the filtered set is smaller. The model ranks at most 20 candidates.
2. Low, medium, and high are tertiles of parsed cost-for-two. Ingest stores the rupee edges and the form displays them.
3. `bangalore` and `bengaluru` keep the whole catalog. Any other location must match the neighborhood, or else a `listed_in(city)` value. Address is not a filter.
4. Duplicate listings collapse on normalized name plus address. The highest-vote listing supplies rating, votes, cost, and url. Cuisines, restaurant types, liked dishes, and listing areas are unions.
5. A rating string counts when it contains a number from 0 to 5. Every other distinct `rate` value is recorded on the ingest manifest.
6. The model host for this project is Groq’s OpenAI-compatible API at `https://api.groq.com/openai/v1`. `LLM_MODEL` names the Groq model; the production model this service is set up for is `openai/gpt-oss-120b`. A missing configuration, a failed call, or an invalid response returns the filtered list ordered by rating and votes, with a sentence built from the row. The API key stays in the environment.
7. An extra preference does not add or remove restaurants. The explanation may cite restaurant type, liked dishes, and a 400-character review excerpt.
8. Online order and table booking are shown on the card and sent to the model as evidence. They are not filters.

## How to use this document

The test for a change is the objective above: a person states location, budget, cuisine, minimum rating, and any extra preference, and receives ranked restaurants from this dataset with a reason that matches the row. When a preprocessing rule, a budget cutoff, a result count, or a model choice gets decided, edit it into this file so the project has one context.
