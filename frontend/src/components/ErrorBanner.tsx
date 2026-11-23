export function ErrorBanner({ errors }: { errors: string[] }) {
  if (errors.length === 0) {
    return null;
  }
  return (
    <section className="error-panel">
      <h2>Please correct the following errors before finding restaurants.</h2>
      <ul>
        {errors.map((error) => (
          <li key={error}>{error}</li>
        ))}
      </ul>
    </section>
  );
}
