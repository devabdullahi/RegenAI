import type { Metadata } from "next";
import { Archivo, IBM_Plex_Mono, Source_Serif_4 } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/sonner";

// Archivo carries the chrome: signage-weight grotesk, legible at a glance.
const archivo = Archivo({
  variable: "--font-ui",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

// Source Serif 4 sets the reading matter — program rules explained the way an
// extension bulletin explains them.
const sourceSerif = Source_Serif_4({
  variable: "--font-reading",
  subsets: ["latin"],
  weight: ["400", "600"],
});

// Every figure and code: acres, bu/ac, county FIPS, CPS 340.
const plexMono = IBM_Plex_Mono({
  variable: "--font-data",
  subsets: ["latin"],
  weight: ["400", "500"],
});

import type { Viewport } from "next";

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export const metadata: Metadata = {
  title: "RegenAI — Smarter Farming Decisions",
  description:
    "AI-powered recommendations for regenerative agriculture. Track EQIP eligibility and carbon credits for your farm.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${archivo.variable} ${sourceSerif.variable} ${plexMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-card focus:text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        >
          Skip to main content
        </a>
        {children}
        <Toaster position="top-center" richColors />
      </body>
    </html>
  );
}
