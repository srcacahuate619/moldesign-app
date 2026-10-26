import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
const state = vi.hoisted(() => ({ locale: "es" as "es" | "en", theme: "dark", user: { user_id: "qa2" } }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("../../../lib/auth", () => ({ useAuth: () => ({ user: state.user }) }));
vi.mock("../../../context/ThemeContext", () => ({ useTheme: () => ({ theme: state.theme, toggleTheme: vi.fn() }) }));
vi.mock("../../../context/LanguageContext", async (importOriginal) => {
 const actual = await importOriginal<typeof import("../../../context/LanguageContext")>();
 const t = (key: string) => actual.TRANSLATIONS[state.locale][key] ?? key;
 return { ...actual, useLanguage: () => ({ locale: state.locale, t, setLocale: vi.fn(), currentLanguage: actual.LANGUAGES.find(l => l.code === state.locale) }) };
});
vi.mock("../LegalModal", () => ({ LegalModal: () => null }));
vi.mock("../AboutModal", () => ({ AboutModal: () => null }));
import { OptionsMenu } from "../OptionsMenu";

describe("QA2-003: el nombre del tema se traduce completo", () => {
 it.each([
  { locale: "es" as const, theme: "dark", label: "Tema oscuro" },
  { locale: "es" as const, theme: "light", label: "Tema claro" },
  { locale: "en" as const, theme: "dark", label: "Dark theme" },
  { locale: "en" as const, theme: "light", label: "Light theme" },
 ])("$locale/$theme: $label", async ({locale,theme,label}) => {
  state.locale=locale;state.theme=theme;
  render(<OptionsMenu isOpen onClose={vi.fn()} />);
  expect(await screen.findByRole("button",{name:label})).toBeInTheDocument();
 });
});