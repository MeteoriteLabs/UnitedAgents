"use client";
import { Moon, Sun } from "lucide-react";
import { useState, useEffect } from "react";

export function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("ua_theme");
    if (stored === "dark" || (!stored && window.matchMedia("(prefers-color-scheme: dark)").matches)) {
      setDark(true);
      document.documentElement.classList.add("dark");
    }
  }, []);

  function toggle() {
    const next = !dark;
    setDark(next);
    if (next) {
      document.documentElement.classList.add("dark");
      localStorage.setItem("ua_theme", "dark");
    } else {
      document.documentElement.classList.remove("dark");
      localStorage.setItem("ua_theme", "light");
    }
  }

  return (
    <button
      onClick={toggle}
      className="rounded-full p-1.5 hover:bg-[var(--color-muted-bg)] transition-colors"
      aria-label="Toggle theme"
      data-testid="theme-toggle"
    >
      {dark ? <Sun className="h-4 w-4 text-[var(--color-muted)]" /> : <Moon className="h-4 w-4 text-[var(--color-muted)]" />}
    </button>
  );
}
