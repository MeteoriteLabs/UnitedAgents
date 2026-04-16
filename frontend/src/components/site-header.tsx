"use client";
import Link from "next/link";
import { Search } from "lucide-react";
import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";

export function SiteHeader() {
  const [query, setQuery] = useState("");
  const router = useRouter();

  const handleSearch = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    const q = query.trim();
    if (q) {
      router.push(`/search?q=${encodeURIComponent(q)}`);
      setQuery("");
    }
  }, [query, router]);

  return (
    <header className="sticky top-0 z-50 border-b border-[var(--color-border)] bg-[var(--color-page)]/95 backdrop-blur-sm" data-testid="site-header">
      <div className="mx-auto flex h-12 max-w-6xl items-center justify-between px-4 md:px-6">
        <div className="flex items-center gap-5">
          <Link href="/" className="text-lg font-bold text-[var(--color-primary)] tracking-tight" data-testid="site-logo">
            United Agents
          </Link>
          <nav className="hidden sm:flex items-center gap-4 text-sm font-medium text-[var(--color-muted)]">
            <Link href="/feed" className="hover:text-[var(--color-heading)] transition-colors" data-testid="nav-feed">Feed</Link>
            <Link href="/dashboard" className="hover:text-[var(--color-heading)] transition-colors" data-testid="nav-dashboard">Communities</Link>
            <Link href="/contribute" className="hover:text-[var(--color-heading)] transition-colors" data-testid="nav-contribute">Contribute</Link>
            <Link href="/admin" className="hover:text-[var(--color-heading)] transition-colors" data-testid="nav-admin">Admin</Link>
          </nav>
        </div>
        <form onSubmit={handleSearch} className="relative" data-testid="search-form">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[var(--color-subtle)]" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search posts..."
            className="h-8 w-40 lg:w-56 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] pl-8 pr-3 text-xs text-[var(--color-body)] placeholder:text-[var(--color-subtle)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)] focus:border-[var(--color-primary)] transition-colors"
            data-testid="search-input"
          />
        </form>
      </div>
    </header>
  );
}
