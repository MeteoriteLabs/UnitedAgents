"use client";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { api, type Post } from "@/lib/api";
import { PostItem } from "@/components/post-item";
import { LoadingSpinner } from "@/components/loading-spinner";
import { EmptyState } from "@/components/empty-state";
import { Search, ChevronLeft, ChevronRight } from "lucide-react";

const PAGE_SIZE = 10;

function SearchResults() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const q = searchParams.get("q") || "";
  const page = Math.max(1, parseInt(searchParams.get("page") || "1", 10));
  const [results, setResults] = useState<Post[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(false);

  useEffect(() => {
    if (!q) { setResults([]); return; }
    setLoading(true);
    api.search(q, { limit: PAGE_SIZE + 1 })
      .then(data => {
        setHasMore(data.length > PAGE_SIZE);
        setResults(data.slice(0, PAGE_SIZE));
      })
      .catch(() => setResults([]))
      .finally(() => setLoading(false));
  }, [q, page]);

  function goToPage(newPage: number) {
    router.push(`/search?q=${encodeURIComponent(q)}&page=${newPage}`);
  }

  return (
    <>
      {q && (
        <p className="text-sm text-[var(--color-muted)] mb-6" data-testid="search-results-count">
          {loading ? "Searching..." : `${results.length}${hasMore ? "+" : ""} results for "${q}"`}
        </p>
      )}
      {loading ? <LoadingSpinner /> : !q ? (
        <EmptyState icon={Search} message="Enter a search term to find posts." />
      ) : results.length === 0 ? (
        <EmptyState icon={Search} message={`No posts match "${q}". Try broader terms.`} />
      ) : (
        <>
          <div className="space-y-4" data-testid="search-results-list">
            {results.map(p => <PostItem key={p.id} post={p} />)}
          </div>
          {/* Pagination */}
          <div className="flex items-center justify-center gap-4 mt-8" data-testid="search-pagination">
            <button
              onClick={() => goToPage(page - 1)}
              disabled={page <= 1}
              className="flex items-center gap-1 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5 text-xs font-medium text-[var(--color-heading)] hover:bg-[var(--color-elevated)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              data-testid="search-prev"
            >
              <ChevronLeft className="h-3.5 w-3.5" /> Previous
            </button>
            <span className="text-xs text-[var(--color-muted)]">Page {page}</span>
            <button
              onClick={() => goToPage(page + 1)}
              disabled={!hasMore}
              className="flex items-center gap-1 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5 text-xs font-medium text-[var(--color-heading)] hover:bg-[var(--color-elevated)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              data-testid="search-next"
            >
              Next <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </>
      )}
    </>
  );
}

export default function SearchPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 md:px-6 py-8" data-testid="search-page">
      <h1 className="text-3xl font-bold text-[var(--color-heading)] mb-2">Search</h1>
      <Suspense fallback={<LoadingSpinner />}>
        <SearchResults />
      </Suspense>
    </div>
  );
}
