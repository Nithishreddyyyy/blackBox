"use client";

import { useEffect, useState } from "react";

export default function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    if (typeof window === "undefined") return "light";
    return (localStorage.getItem("theme") as "light" | "dark" | null) || "light";
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  function toggleTheme() {
    const newTheme = theme === "light" ? "dark" : "light";
    setTheme(newTheme);
    document.documentElement.setAttribute("data-theme", newTheme);
    localStorage.setItem("theme", newTheme);
  }

  return (
    <button
      type="button"
      className="btn btn-secondary btn-sm"
      onClick={toggleTheme}
      style={{ position: "fixed", top: 10, right: 10, zIndex: 1000 }}
    >
      {theme === "light" ? "Dark mode" : "Light mode"}
    </button>
  );
}
