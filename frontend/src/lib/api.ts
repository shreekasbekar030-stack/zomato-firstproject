import type { Meta, Recommendation } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export async function loadMeta(): Promise<Meta> {
  const response = await fetch(`${API_URL}/api/meta`);
  if (!response.ok) {
    throw new Error("The catalog did not load.");
  }
  return response.json() as Promise<Meta>;
}

export async function recommend(values: {
  location: string;
  budget: string;
  cuisine: string;
  minRating: string;
  extra: string;
}): Promise<{ status: number; errors: string[]; result: Recommendation | null }> {
  const response = await fetch(`${API_URL}/api/recommendations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      location: values.location,
      budget: values.budget,
      cuisine: values.cuisine,
      min_rating: values.minRating,
      extra: values.extra,
    }),
  });
  const body = (await response.json()) as Recommendation & { errors?: string[] };
  if (!response.ok) {
    return { status: response.status, errors: body.errors ?? ["The search could not be completed."], result: null };
  }
  return { status: response.status, errors: [], result: body };
}
