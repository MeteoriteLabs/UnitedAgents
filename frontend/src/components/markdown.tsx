import ReactMarkdown from "react-markdown";

export function Markdown({ content }: { content: string }) {
  return (
    <div className="prose prose-stone max-w-none" data-testid="markdown-content">
      <ReactMarkdown
        components={{
          h1: ({ children }) => <h1 className="text-2xl font-bold text-[var(--color-heading)] mt-6 mb-3">{children}</h1>,
          h2: ({ children }) => <h2 className="text-xl font-semibold text-[var(--color-heading)] mt-5 mb-2">{children}</h2>,
          h3: ({ children }) => <h3 className="text-lg font-semibold text-[var(--color-heading)] mt-4 mb-2">{children}</h3>,
          p: ({ children }) => <p className="text-[var(--color-body)] leading-relaxed mb-3">{children}</p>,
          a: ({ href, children }) => (
            <a href={href} className="text-[var(--color-primary)] hover:underline" target={href?.startsWith("http") ? "_blank" : undefined} rel={href?.startsWith("http") ? "noopener" : undefined}>
              {children}
            </a>
          ),
          ul: ({ children }) => <ul className="list-disc pl-5 mb-3 space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-5 mb-3 space-y-1">{children}</ol>,
          li: ({ children }) => <li className="text-[var(--color-body)]">{children}</li>,
          code: ({ children, className }) => {
            const isBlock = className?.includes("language-");
            if (isBlock) {
              return <code className="block bg-[var(--color-muted-bg)] rounded p-3 text-sm font-mono overflow-x-auto">{children}</code>;
            }
            return <code className="bg-[var(--color-muted-bg)] rounded px-1.5 py-0.5 text-sm font-mono">{children}</code>;
          },
          blockquote: ({ children }) => (
            <blockquote className="border-l-3 border-[var(--color-primary)] pl-4 italic text-[var(--color-muted)]">{children}</blockquote>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
