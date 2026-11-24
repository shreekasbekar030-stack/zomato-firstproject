import type { Ref } from "react";

const FIELD_LINKS = [
  { needle: "location", href: "#location" },
  { needle: "budget", href: "#budget" },
  { needle: "cuisine", href: "#cuisine" },
  { needle: "rating", href: "#min_rating" },
  { needle: "extra preference", href: "#extra" },
];

export function ErrorBanner({ errors, summaryRef }: { errors: string[]; summaryRef?: Ref<HTMLElement> }) {
  if (errors.length === 0) {
    return null;
  }
  return (
    <section className="error-panel" role="alert" tabIndex={-1} ref={summaryRef} aria-labelledby="error-title">
      <h2 id="error-title">Please correct the following errors before finding restaurants.</h2>
      <ul>
        {errors.map((error) => {
          const href = fieldHref(error);
          return <li key={error}>{href ? <a href={href}>{error}</a> : error}</li>;
        })}
      </ul>
    </section>
  );
}

function fieldHref(error: string) {
  const text = error.toLowerCase();
  return FIELD_LINKS.find((item) => text.includes(item.needle))?.href;
}
