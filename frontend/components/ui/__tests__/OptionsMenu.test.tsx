import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
const routerPush = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: routerPush }) }));
import { OptionsMenu } from "../OptionsMenu";

vi.mock("../../../lib/auth", () => ({
  useAuth: () => ({ user: { user_id: "test-user" } }),
}));

vi.mock("../../../context/ThemeContext", () => ({
  useTheme: () => ({ theme: "dark", toggleTheme: vi.fn() }),
}));

vi.mock("../../../context/LanguageContext", () => ({
  LANGUAGES: [
    { code: "es", flag: "🇲🇽", name: "Español" },
    { code: "en", flag: "🇺🇸", name: "English" },
  ],
  useLanguage: () => ({
    locale: "es",
    setLocale: vi.fn(),
    currentLanguage: { code: "es", flag: "🇲🇽", name: "Español" },
  }),
}));

vi.mock("../LegalModal", () => ({ LegalModal: () => null }));
vi.mock("../AboutModal", () => ({ AboutModal: () => null }));
vi.mock("../LocalAISettingsModal", () => ({ LocalAISettingsModal: () => null }));
vi.mock("../CloudAISettingsModal", () => ({ CloudAISettingsModal: () => null }));

describe("OptionsMenu", () => {
  it("mantiene Soporte como la última vista del mismo drawer", async () => {
    render(<OptionsMenu isOpen onClose={vi.fn()} />);

    expect(await screen.findByRole("heading", { name: "Opciones" })).toBeInTheDocument();
    expect(screen.queryByText("Preguntas frecuentes")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Soporte y ayuda" }));

    expect(await screen.findByRole("heading", { name: "Soporte" })).toBeInTheDocument();
    expect(screen.getByText("Preguntas frecuentes")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Volver a Opciones" }));
    expect(await screen.findByRole("heading", { name: "Opciones" })).toBeInTheDocument();
  });

  it("cierra con Escape y devuelve el foco al disparador", async () => {
    const onClose = vi.fn();
    const trigger = document.createElement("button");
    document.body.appendChild(trigger);
    const triggerRef = { current: trigger } as React.RefObject<HTMLButtonElement>;
    const { rerender } = render(<OptionsMenu isOpen onClose={onClose} triggerRef={triggerRef} />);

    await screen.findByRole("heading", { name: "Opciones" });
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);

    rerender(<OptionsMenu isOpen={false} onClose={onClose} triggerRef={triggerRef} />);
    await waitFor(() => expect(trigger).toHaveFocus());
    trigger.remove();
  });
});
