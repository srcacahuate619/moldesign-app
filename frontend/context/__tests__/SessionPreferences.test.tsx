import type { ReactNode } from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const authState = vi.hoisted(() => ({
  isLoading: false,
  user: null as { user_id: string } | null,
}));

vi.mock("../../lib/auth", () => ({ useAuth: () => authState }));

import { LanguageProvider, useLanguage } from "../LanguageContext";
import { ThemeProvider, useTheme } from "../ThemeContext";

const themeWrapper = ({ children }: { children: ReactNode }) => <ThemeProvider>{children}</ThemeProvider>;
const languageWrapper = ({ children }: { children: ReactNode }) => <LanguageProvider>{children}</LanguageProvider>;

describe("preferencias visuales por sesión", () => {
  beforeEach(() => {
    authState.isLoading = false;
    authState.user = null;
  });

  it("el tema de Alice no sobrescribe el tema guardado de Bob al cambiar de cuenta", async () => {
    localStorage.setItem("moldesign_theme:user:alice", "light");
    localStorage.setItem("moldesign_theme:user:bob", "dark");
    authState.user = { user_id: "alice" };
    const { result, rerender } = renderHook(() => useTheme(), { wrapper: themeWrapper });
    await waitFor(() => expect(result.current.theme).toBe("light"));

    authState.user = { user_id: "bob" };
    rerender();

    await waitFor(() => expect(result.current.theme).toBe("dark"));
    expect(localStorage.getItem("moldesign_theme:user:bob")).toBe("dark");
    expect(localStorage.getItem("moldesign_theme:user:alice")).toBe("light");
  });

  it("cambiar el tema sólo modifica la preferencia de la cuenta activa", async () => {
    localStorage.setItem("moldesign_theme:user:alice", "dark");
    localStorage.setItem("moldesign_theme:user:bob", "dark");
    authState.user = { user_id: "bob" };
    const { result } = renderHook(() => useTheme(), { wrapper: themeWrapper });
    await waitFor(() => expect(result.current.theme).toBe("dark"));

    act(() => result.current.setTheme("light"));
    await waitFor(() => expect(localStorage.getItem("moldesign_theme:user:bob")).toBe("light"));
    expect(localStorage.getItem("moldesign_theme:user:alice")).toBe("dark");
  });

  it("idioma se carga y persiste de forma independiente", async () => {
    localStorage.setItem("moldesign_locale:user:alice", "es");
    localStorage.setItem("moldesign_locale:user:bob", "en");
    authState.user = { user_id: "alice" };
    const { result, rerender } = renderHook(() => useLanguage(), { wrapper: languageWrapper });
    await waitFor(() => expect(result.current.locale).toBe("es"));

    authState.user = { user_id: "bob" };
    rerender();
    await waitFor(() => expect(result.current.locale).toBe("en"));
    act(() => result.current.setLocale("es"));

    await waitFor(() => expect(localStorage.getItem("moldesign_locale:user:bob")).toBe("es"));
    expect(localStorage.getItem("moldesign_locale:user:alice")).toBe("es");
  });

  it("sin sesión los cambios no crean claves globales compartidas", async () => {
    const { result } = renderHook(() => useTheme(), { wrapper: themeWrapper });
    await waitFor(() => expect(result.current.theme).toBe("dark"));
    act(() => result.current.setTheme("light"));

    expect(localStorage.getItem("moldesign_theme")).toBeNull();
    expect([...Array(localStorage.length)].map((_, index) => localStorage.key(index))).toEqual([]);
  });
});
