"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Markdown } from "@/components/markdown";
import { LoadingSpinner } from "@/components/loading-spinner";

export default function ContributePage() {
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getSkillMd().then(setContent).catch(() => setContent("# Unable to load skill file\n\nPlease try again later.")).finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner />;

  return (
    <div className="mx-auto max-w-4xl px-4 md:px-6 py-8" data-testid="contribute-page">
      <Markdown content={content} />
    </div>
  );
}
