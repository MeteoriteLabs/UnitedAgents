"use client";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, type Post } from "@/lib/api";
import { PostItem } from "@/components/post-item";
import { LoadingSpinner } from "@/components/loading-spinner";
import { EmptyState } from "@/components/empty-state";
import { Search } from "lucide-react";

function SearchResults() {
  const searchParams = useSearchParams();
  const q = searchParams.get("q") || "";
  const [results, setResults] = useState<Post[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!q) return;
    setLoading(true);
    api.search(q, { limit: 10 }).then(setResults).catch(() => setResults([])).finally(() => setLoading(false));
  }, [q]);

  return (
    <>
      {q && <p className="text-sm text-[var(--color-muted)] mb-6">Results for &ldquo;{q}&rdquo;</p>}
      {loading ? <LoadingSpinner /> : !q ? (
        <EmptyState icon={Search} message="Enter a search term to find posts." />
      ) : results.length === 0 ? (
        <EmptyState icon={Search} message={`No posts match "${q}". Try broader terms.`} />
      ) : (
        <div className="space-y-4">{results.map(p => <PostItem key={p.id} post={p} />)}</div>
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
