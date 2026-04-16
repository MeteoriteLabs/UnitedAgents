import type { Metadata } from "next";
import "./globals.css";

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
      <head>
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
        />
      </head>
      <body className="min-h-screen bg-[var(--color-page)] text-[var(--color-body)] antialiased">
        {children}
      </body>
    </html>
  );
}
