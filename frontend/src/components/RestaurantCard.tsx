import type { Card } from "@/lib/types";

export function RestaurantCard({ card, rank }: { card: Card; rank: number }) {
  return (
    <article className="card">
      <p className="rank">{rank}</p>
      <h2>{card.url ? <a href={card.url}>{card.name}</a> : card.name}</h2>
      <p className="cuisines">{card.cuisines.join(", ")}</p>
      <p className="rating">
        Rated {card.rating} from {card.votes} votes
      </p>
      <p className="cost">About ₹{card.costForTwo} for two</p>
      <p className="neighborhood">{card.location}</p>
      <div className="flags">
        <span>Online order: {card.onlineOrder ? "yes" : "no"}</span>
        <span>Table booking: {card.bookTable ? "yes" : "no"}</span>
      </div>
      <p className="explanation">{card.explanation}</p>
    </article>
  );
}
