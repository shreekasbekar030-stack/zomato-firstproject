import type { FormValues, Meta } from "@/lib/types";

const CUISINES = [
  "Chinese",
  "Italian",
  "North Indian",
  "South Indian",
  "Fast Food",
  "Biryani",
  "Continental",
  "Cafe",
];

type Props = {
  meta: Meta | null;
  values: FormValues;
  errors: string[];
  pending: boolean;
  onChange: (values: FormValues) => void;
  onSubmit: () => void;
};

export function PreferenceForm({ meta, values, errors, pending, onChange, onSubmit }: Props) {
  const low = meta?.costP33;
  const high = meta?.costP66;
  const bands =
    low == null || high == null
      ? [
          ["low", "Low"],
          ["medium", "Medium"],
          ["high", "High"],
        ]
      : [
          ["low", `Low (at or under ₹${low} for two)`],
          ["medium", `Medium (₹${low}–₹${high} for two)`],
          ["high", `High (above ₹${high} for two)`],
        ];

  function set<K extends keyof FormValues>(key: K, value: FormValues[K]) {
    onChange({ ...values, [key]: value });
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <div className={fieldClass(errors, "location")}>
        <div className="label-row">
          <label htmlFor="location">Location</label>
          <span className="req">Required</span>
        </div>
        <select id="location" value={values.location} onChange={(event) => set("location", event.target.value)}>
          <option value="">Choose a location</option>
          {(meta?.locations ?? ["Bangalore", "Bengaluru"]).map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
        <p className="hint">Bangalore and Bengaluru include every neighborhood.</p>
      </div>
      <div className={fieldClass(errors, "budget")}>
        <div className="label-row">
          <label htmlFor="budget">Budget</label>
          <span className="req">Required</span>
        </div>
        <select id="budget" value={values.budget} onChange={(event) => set("budget", event.target.value)}>
          <option value="">Choose a budget</option>
          {bands.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <p className="hint">Approximate cost for two people.</p>
      </div>
      <div className={`field span${mentions(errors, "cuisine") ? " bad" : ""}`}>
        <div className="label-row">
          <label htmlFor="cuisine">Cuisine</label>
        </div>
        <input
          id="cuisine"
          value={values.cuisine}
          placeholder="Or type one cuisine"
          onChange={(event) => set("cuisine", event.target.value)}
        />
        <div className="picks">
          {CUISINES.map((name) => (
            <button
              key={name}
              type="button"
              className={values.cuisine === name ? "on" : undefined}
              onClick={() => set("cuisine", values.cuisine === name ? "" : name)}
            >
              {name}
            </button>
          ))}
        </div>
        <p className="hint">Optional. Choose one cuisine, or leave this blank to include every cuisine.</p>
      </div>
      <div className={fieldClass(errors, "rating")}>
        <div className="label-row">
          <label htmlFor="min_rating">Minimum rating</label>
        </div>
        <input
          id="min_rating"
          inputMode="decimal"
          value={values.minRating}
          placeholder="4"
          onChange={(event) => set("minRating", event.target.value)}
        />
        <p className="hint">A number from 0 to 5.</p>
      </div>
      <div className={`field span${mentions(errors, "extra preference") ? " bad" : ""}`}>
        <div className="label-row">
          <label htmlFor="extra">Extra preference</label>
        </div>
        <textarea
          id="extra"
          rows={3}
          value={values.extra}
          placeholder="Family-friendly or quick service"
          onChange={(event) => set("extra", event.target.value)}
        />
        <p className="hint">Optional. This does not filter the list.</p>
      </div>
      <button className="span" type="submit" disabled={pending}>
        {pending ? "Finding restaurants…" : "Find restaurants"}
      </button>
    </form>
  );
}

function fieldClass(errors: string[], needle: string) {
  return mentions(errors, needle) ? "field bad" : "field";
}

function mentions(errors: string[], needle: string) {
  return errors.some((error) => error.toLowerCase().includes(needle));
}
