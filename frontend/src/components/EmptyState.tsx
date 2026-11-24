import type { Preferences } from "@/lib/types";
import { ForkIcon } from "./Icons";

export function EmptyState({ preferences }: { preferences: Preferences }) {
  return (
    <section className="empty">
      <div className="empty-mark">
        <ForkIcon />
      </div>
      <h2>No restaurants match</h2>
      <p>No restaurants match location, budget, cuisine, and minimum rating.</p>
      <p>Try one cuisine, a wider budget, or a lower minimum rating.</p>
      <div className="facts">
        <p>Location: {preferences.location}</p>
        <p>Budget: {preferences.budget}</p>
        <p>Cuisine: {preferences.cuisine}</p>
        <p>Minimum rating: {preferences.minRating}</p>
      </div>
    </section>
  );
}
