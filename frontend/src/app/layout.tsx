import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { SiteHeader } from "@/components/SiteHeader";

import "./globals.css";

const inter = Inter({ subsets: ["latin"], weight: ["400", "500", "600", "700"] });

export const metadata: Metadata = {
  title: "Find a restaurant",
  description: "Search Bangalore restaurants by location, budget, cuisine, and minimum rating.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <SiteHeader />
        <main className="wrap">{children}</main>
      </body>
    </html>
  );
}
