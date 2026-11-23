# Catalog manifest

Copied from the ingest printout for the train split of `ManikaSaini/zomato-restaurant-recommendation`. The source file is `zomato.csv` at commit `5738e9eda2fad49ad51c6e0ed26e761d9b947133`, 574,072,999 bytes. These numbers are from that run.

```json
{
  "dataset": "ManikaSaini/zomato-restaurant-recommendation",
  "built_at": "2026-11-18T18:48:36.297255+00:00",
  "source_rows": 51717,
  "restaurant_count": 12494,
  "dropped_blank_identity": 0,
  "missing_rating": 3003,
  "missing_cost": 62,
  "unparsed_rate_values": [
    "NEW",
    "",
    "-"
  ],
  "cost_p33": 300,
  "cost_p66": 2000
}
```

`source_rows` is the train split size. `restaurant_count` is smaller because duplicate listings collapsed. The unparsed `rate` strings are `NEW`, a blank value, and `-`. None of them contains a numeric score.
