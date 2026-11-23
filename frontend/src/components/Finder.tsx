"use client";

import { useEffect, useState } from "react";

import { loadMeta, recommend } from "@/lib/api";
import type { FormValues, Meta, Recommendation } from "@/lib/types";

import { EmptyState } from "./EmptyState";
import { ErrorBanner } from "./ErrorBanner";
import { InfoIcon } from "./Icons";
import { PreferenceForm } from "./PreferenceForm";
import { RestaurantCard } from "./RestaurantCard";

const EMPTY_FORM: FormValues = { location: "", budget: "", cuisine: "", minRating: "", extra: "" };

export function Finder() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [values, setValues] = useState<FormValues>(EMPTY_FORM);
  const [errors, setErrors] = useState<string[]>([]);
  const [offline, setOffline] = useState("");
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState<Recommendation | null>(null);

  useEffect(() => {
    let active = true;
    loadMeta()
      .then((payload) => {
        if (active) {
          setMeta(payload);
        }
      })
      .catch(() => {
        if (active) {
          setOffline("The catalog service is not running. Start it, then refresh this page.");
        }
      });
    return () => {
      active = false;
    };
  }, []);

  async function onSubmit() {
    setPending(true);
    setOffline("");
    try {
      const response = await recommend(values);
      setErrors(response.errors);
      setResult(response.result);
    } catch {
      setErrors([]);
      setResult(null);
      setOffline("The search could not reach the catalog service.");
    } finally {
      setPending(false);
    }
  }

  const wide = result !== null;
  const count = result && !result.empty ? result.cards.length : 0;

  return (
    <>
      {offline ? <p className="status">{offline}</p> : null}
      <ErrorBanner errors={errors} />
      <div className={wide ? "stage wide" : "stage"}>
        <section className="finder">
          {wide ? (
            <div className="panel">
              <h2>Preferences</h2>
              <p className="quiet">Change a field and search again.</p>
              <BudgetText text={meta?.budgetText} />
            </div>
          ) : (
            <>
              <header>
                <p className="mark">Restaurant finder</p>
                <h1>Find a restaurant</h1>
                <p className="lede">Search Bangalore restaurants by location, budget, cuisine, and minimum rating.</p>
              </header>
              <BudgetText text={meta?.budgetText} />
            </>
          )}
          <PreferenceForm
            meta={meta}
            values={values}
            errors={errors}
            pending={pending}
            onChange={setValues}
            onSubmit={onSubmit}
          />
        </section>
        {result?.empty ? <EmptyState preferences={result.preferences} /> : null}
        {result && !result.empty ? (
          <section className="results">
            <h2>{count === 1 ? "1 restaurant" : `${count} restaurants`}</h2>
            {result.summary ? <p className="summary">{result.summary}</p> : null}
            {result.notice ? <p className="notice">{result.notice}</p> : null}
            <ol className="cards">
              {result.cards.map((card, index) => (
                <li key={`${card.name}-${card.location}`}>
                  <RestaurantCard card={card} rank={index + 1} />
                </li>
              ))}
            </ol>
          </section>
        ) : null}
      </div>
    </>
  );
}

function BudgetText({ text }: { text: string | undefined }) {
  return (
    <div className="edges">
      <InfoIcon />
      <p>
        <strong>Budget for two</strong>
        {text ?? "Budget edges are loading."}
      </p>
    </div>
  );
}
