export function LoadingSpinner({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  const dims = { sm: "h-4 w-4", md: "h-6 w-6", lg: "h-8 w-8" };
  return (
    <div className="flex items-center justify-center py-8" data-testid="loading-spinner">
      <div className={`${dims[size]} animate-spin rounded-full border-2 border-[var(--color-border)] border-t-[var(--color-primary)]`} />
    </div>
  );
}
