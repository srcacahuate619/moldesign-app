"use client";
import React, { createContext, useContext, useState, useEffect } from "react";
import { useAuth } from "../lib/auth";
import { getUserItem, setUserItem } from "../lib/userStorage";

type Theme = "dark" | "light";

interface ThemeContextProps {
  theme: Theme;
  setTheme: (t: Theme) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextProps | undefined>(undefined);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const { isLoading: authLoading, user } = useAuth();
  const [theme, setThemeState] = useState<Theme>("dark");
  const [hydrated, setHydrated] = useState(false);
  const [loadedOwnerId, setLoadedOwnerId] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    const saved = getUserItem("moldesign_theme", user?.user_id) as Theme | null;
    setThemeState("dark");
    if (saved === "light" || saved === "dark") {
      setThemeState(saved);
    }
    setLoadedOwnerId(user?.user_id ?? null);
    setHydrated(true);
  }, [authLoading, user?.user_id]);

  useEffect(() => {
    if (!hydrated) return;
    if (user && loadedOwnerId === user.user_id) {
      setUserItem("moldesign_theme", theme, user.user_id);
    }
    document.documentElement.classList.toggle("light", theme === "light");
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme, hydrated, loadedOwnerId, user]);

  const setTheme = (t: Theme) => {
    if (typeof document !== "undefined" && document.startViewTransition) {
      document.startViewTransition(() => {
        setThemeState(t);
      });
    } else {
      setThemeState(t);
    }
  };

  const toggleTheme = () => setTheme(theme === "dark" ? "light" : "dark");

  if (!hydrated) {
    return (
      <ThemeContext.Provider value={{ theme: "dark", setTheme: () => {}, toggleTheme: () => {} }}>
        {children}
      </ThemeContext.Provider>
    );
  }

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within a ThemeProvider");
  return ctx;
}
