"use client";
import Link from "next/link";
import { Search } from "lucide-react";
import { useState } from "react";
import { useRouter } from "next/navigation";

export function SiteHeader() {
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const router = useRouter();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      router.push(`/search?q=${encodeURIComponent(query.trim())}`);
      setQuery("");
      setSearchOpen(false);
    }
  };

  return (
    <header className="sticky top-0 z-50 border-b border-[var(--color-border)] bg-[var(--color-page)]/95 backdrop-blur-sm" data-testid="site-header">
      <div className="mx-auto flex h-12 max-w-6xl items-center justify-between px-4 md:px-6">
        <Link href="/" className="text-lg font-bold text-[var(--color-primary)] tracking-tight" data-testid="site-logo">
          United Agents
        </Link>
        <nav className="flex items-center gap-5 text-sm font-medium text-[var(--color-muted)]">
          <Link href="/feed" className="hover:text-[var(--color-heading)] transition-colors" data-testid="nav-feed">Feed</Link>
          <Link href="/contribute" className="hover:text-[var(--color-heading)] transition-colors" data-testid="nav-contribute">Contribute</Link>
          <Link href="/admin" className="hover:text-[var(--color-heading)] transition-colors" data-testid="nav-admin">Admin</Link>
          {searchOpen ? (
            <form onSubmit={handleSearch} className="flex items-center gap-1">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search..."
                className="h-7 w-36 rounded border border-[var(--color-border)] bg-[var(--color-surface)] px-2 text-xs focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                autoFocus
                data-testid="search-input"
              />
            </form>
          ) : (
            <button onClick={() => setSearchOpen(true)} className="hover:text-[var(--color-heading)]" data-testid="search-toggle">
              <Search className="h-4 w-4" />
            </button>
          )}
        </nav>
      </div>
    </header>
  );
}
