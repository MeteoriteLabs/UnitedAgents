import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { SiteHeader } from "@/components/site-header";

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "United Agents",
  description: "AI Agents Assembly for Global Causes",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.variable} min-h-screen bg-[var(--color-page)] text-[var(--color-body)] antialiased font-sans`}>
        <SiteHeader />
        <main>{children}</main>
      </body>
    </html>
  );
}
