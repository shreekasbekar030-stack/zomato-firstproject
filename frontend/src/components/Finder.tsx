"use client";

import { useEffect, useState } from "react";
import { AnimatePresence } from "motion/react";
import { ReducedMotionConfig } from "@animate-ui/react/utils/motion";

import { loadMeta, recommend } from "@/lib/api";
import type { FormValues, Meta, Recommendation } from "@/lib/types";

import { EmptyState } from "./EmptyState";
import { InfoIcon } from "./Icons";
import { ResultItem, SoftLine, StatusBanner } from "./motion";
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
      <StatusBanner open={offline.length > 0}>
        <p className="status" role="alert">{offline}</p>
      </StatusBanner>
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
                <SoftLine className="lede">Search Bangalore restaurants by location, budget, cuisine, and minimum rating.</SoftLine>
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
            <ReducedMotionConfig>
              <ol className="cards">
                <AnimatePresence>
                  {result.cards.map((card, index) => (
                    <ResultItem key={`${card.name}-${card.location}`} index={index}>
                      <RestaurantCard card={card} rank={index + 1} />
                    </ResultItem>
                  ))}
                </AnimatePresence>
              </ol>
            </ReducedMotionConfig>
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
