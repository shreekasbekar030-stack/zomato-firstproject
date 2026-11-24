import type { Metadata } from "next";
import { Karla, Playfair_Display_SC } from "next/font/google";

import { SiteHeader } from "@/components/SiteHeader";

import "./globals.css";

const karla = Karla({ subsets: ["latin"], weight: ["400", "500", "600", "700"] });
const display = Playfair_Display_SC({ subsets: ["latin"], weight: ["400", "700"], variable: "--font-display" });

export const metadata: Metadata = {
  title: "Find a restaurant",
  description: "Search Bangalore restaurants by location, budget, cuisine, and minimum rating.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={display.variable}>
      <body className={karla.className}>
        <SiteHeader />
        <main className="wrap">{children}</main>
      </body>
    </html>
  );
}
