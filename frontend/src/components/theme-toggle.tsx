/**
 * Theme toggle — built but not used (GOTCHAS §6.3).
 * Preserved for future dark mode support (FUTURE_WORK.md).
 */
"use client";
import { Moon, Sun } from "lucide-react";
import { useState } from "react";

export function ThemeToggle() {
  const [dark, setDark] = useState(false);
  return (
    <button
      onClick={() => setDark(!dark)}
      className="rounded-full p-1.5 hover:bg-[var(--color-muted-bg)] transition-colors"
      aria-label="Toggle theme"
      data-testid="theme-toggle"
    >
      {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}
