"use client";

import { useEffect, useRef } from "react";

import type { FormValues, Meta } from "@/lib/types";

import { ErrorBanner } from "./ErrorBanner";
import { CuisineChip, PressButton, StatusBanner } from "./motion";

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

  const summaryRef = useRef<HTMLElement>(null);
  const locationError = messageFor(errors, "location");
  const budgetError = messageFor(errors, "budget");
  const cuisineError = messageFor(errors, "cuisine");
  const ratingError = messageFor(errors, "rating");
  const extraError = messageFor(errors, "extra preference");

  useEffect(() => {
    if (errors.length > 0) {
      summaryRef.current?.focus();
    }
  }, [errors]);

  function set<K extends keyof FormValues>(key: K, value: FormValues[K]) {
    onChange({ ...values, [key]: value });
  }

  return (
    <form
      aria-busy={pending}
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <StatusBanner open={errors.length > 0} className="span">
        <ErrorBanner errors={errors} summaryRef={summaryRef} />
      </StatusBanner>
      <div className={locationError ? "field bad" : "field"}>
        <div className="label-row">
          <label htmlFor="location">Location</label>
          <span className="req">Required</span>
        </div>
        <select
          id="location"
          value={values.location}
          aria-invalid={locationError ? true : undefined}
          aria-describedby={locationError ? "location-hint location-error" : "location-hint"}
          onChange={(event) => set("location", event.target.value)}
        >
          <option value="">Choose a location</option>
          {(meta?.locations ?? ["Bangalore", "Bengaluru"]).map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
        <p id="location-hint" className="hint">Bangalore and Bengaluru include every neighborhood.</p>
        {locationError ? <p id="location-error" className="field-error">{locationError}</p> : null}
      </div>
      <div className={budgetError ? "field bad" : "field"}>
        <div className="label-row">
          <label htmlFor="budget">Budget</label>
          <span className="req">Required</span>
        </div>
        <select
          id="budget"
          value={values.budget}
          aria-invalid={budgetError ? true : undefined}
          aria-describedby={budgetError ? "budget-hint budget-error" : "budget-hint"}
          onChange={(event) => set("budget", event.target.value)}
        >
          <option value="">Choose a budget</option>
          {bands.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <p id="budget-hint" className="hint">Approximate cost for two people.</p>
        {budgetError ? <p id="budget-error" className="field-error">{budgetError}</p> : null}
      </div>
      <div className={`field span${cuisineError ? " bad" : ""}`}>
        <div className="label-row">
          <label htmlFor="cuisine">Cuisine</label>
        </div>
        <input
          id="cuisine"
          value={values.cuisine}
          placeholder="Or type one cuisine"
          aria-invalid={cuisineError ? true : undefined}
          aria-describedby={cuisineError ? "cuisine-hint cuisine-error" : "cuisine-hint"}
          onChange={(event) => set("cuisine", event.target.value)}
        />
        <div className="picks">
          {CUISINES.map((name) => (
            <CuisineChip key={name} selected={values.cuisine === name} onClick={() => set("cuisine", values.cuisine === name ? "" : name)}>
              {name}
            </CuisineChip>
          ))}
        </div>
        <p id="cuisine-hint" className="hint">Optional. Choose one cuisine, or leave this blank to include every cuisine.</p>
        {cuisineError ? <p id="cuisine-error" className="field-error">{cuisineError}</p> : null}
      </div>
      <div className={ratingError ? "field bad" : "field"}>
        <div className="label-row">
          <label htmlFor="min_rating">Minimum rating</label>
        </div>
        <input
          id="min_rating"
          inputMode="decimal"
          value={values.minRating}
          placeholder="4"
          aria-invalid={ratingError ? true : undefined}
          aria-describedby={ratingError ? "rating-hint rating-error" : "rating-hint"}
          onChange={(event) => set("minRating", event.target.value)}
        />
        <p id="rating-hint" className="hint">A number from 0 to 5.</p>
        {ratingError ? <p id="rating-error" className="field-error">{ratingError}</p> : null}
      </div>
      <div className={`field span${extraError ? " bad" : ""}`}>
        <div className="label-row">
          <label htmlFor="extra">Extra preference</label>
        </div>
        <textarea
          id="extra"
          rows={3}
          value={values.extra}
          placeholder="Family-friendly or quick service"
          aria-invalid={extraError ? true : undefined}
          aria-describedby={extraError ? "extra-hint extra-error" : "extra-hint"}
          onChange={(event) => set("extra", event.target.value)}
        />
        <p id="extra-hint" className="hint">Optional. This does not filter the list.</p>
        {extraError ? <p id="extra-error" className="field-error">{extraError}</p> : null}
      </div>
      <PressButton className="span" type="submit" disabled={pending} label={pending ? "Finding restaurants…" : "Find restaurants"} />
    </form>
  );
}

function messageFor(errors: string[], needle: string) {
  return errors.find((error) => error.toLowerCase().includes(needle));
}
