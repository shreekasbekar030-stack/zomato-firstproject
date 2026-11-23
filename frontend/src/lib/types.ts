export type Meta = {
  locations: string[];
  budgetText: string;
  costP33: number | null;
  costP66: number | null;
};

export type Preferences = {
  location: string;
  budget: string;
  cuisine: string;
  minRating: string;
  extra: string;
};

export type Card = {
  name: string;
  url: string;
  cuisines: string[];
  rating: number;
  votes: number;
  costForTwo: number;
  location: string;
  onlineOrder: boolean;
  bookTable: boolean;
  explanation: string;
  explanationFrom: string;
};

export type Recommendation =
  | { empty: true; preferences: Preferences; cards: [] }
  | {
      empty: false;
      source: string;
      summary: string;
      notice: string;
      preferences: Preferences;
      cards: Card[];
    };

export type FormValues = {
  location: string;
  budget: string;
  cuisine: string;
  minRating: string;
  extra: string;
};
