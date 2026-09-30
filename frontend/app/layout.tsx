import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VISHWAS | Forecast Reliability Engine (NCUM-G)",
  description: "Weather Intelligence & Spatiotemporal Hazard Warning Assessment System - AI-Based Forecast Bust Detection via Conformalized Quantile Regression & Linguistic TreeSHAP.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark h-full">
      <body className="h-full bg-slate-900 text-slate-200 antialiased overflow-hidden font-sans">
        {children}
      </body>
    </html>
  );
}
