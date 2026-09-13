// =====================================================================
// Tests para LoginForm — autenticación local-only desktop
// =====================================================================
//
// LoginForm maneja login/registro contra el backend local (FastAPI + SQLite).
// NO usa OAuth externo ni JWT de corta duración — es una app desktop
// offline-first. Validez científica > cualquier otra cosa: el form debe
// mostrar correctamente los campos según mode (login vs register),
// validar submit y manejar estados busy/error.
//
// Tests cubren:
// - mode="login" → muestra email + password, NO username/confirm
// - mode="register" → muestra email + username + password + confirm
// - submit llama onSubmit
// - error prop se renderiza
// - busy=true deshabilita submit button

import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { LoginForm } from "../LoginForm";
import { LanguageProvider } from "../../../context/LanguageContext";

vi.mock("../../../lib/auth", () => ({
  useAuth: () => ({ isLoading: false, user: { user_id: "test-user" } }),
}));

// Helper: renderiza con LanguageProvider (locale forzado a español)
function renderWithLanguage(ui: React.ReactNode) {
  // Setea la preferencia de esta cuenta ANTES del render.
  window.localStorage.setItem("moldesign_locale:user:test-user", "es");
  return render(
    <LanguageProvider>
      {ui}
</LanguageProvider>
  );
}

describe("LoginForm — campos según mode", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  function baseProps(overrides?: Partial<React.ComponentProps<typeof LoginForm>>) {
    return {
      mode: "login" as const,
      setMode: vi.fn(),
      email: "",
      setEmail: vi.fn(),
      username: "",
      setUsername: vi.fn(),
      password: "",
      setPassword: vi.fn(),
      confirmPassword: "",
      setConfirmPassword: vi.fn(),
      busy: false,
      error: null,
      onSubmit: vi.fn(),
      oauthEnabled: false,
      ...overrides,
    };
  }

  it("mode=login → muestra email + password, NO username ni confirmPassword", () => {
    renderWithLanguage(<LoginForm {...baseProps({ mode: "login" })} />);

    expect(screen.getByLabelText(/Email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Contraseña/i)).toBeInTheDocument();

    // Username solo aparece en register
    expect(screen.queryByLabelText(/Usuario/i)).not.toBeInTheDocument();
    // Confirm password solo aparece en register
    expect(screen.queryByLabelText(/Confirmar/i)).not.toBeInTheDocument();
  });

  it("mode=register → muestra email + username + password + confirmPassword", () => {
    renderWithLanguage(<LoginForm {...baseProps({ mode: "register" })} />);

    expect(screen.getByLabelText(/Email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Usuario/i)).toBeInTheDocument();
    // Password y Confirmar Contraseña ambos contienen "Contraseña" → getAllByLabelText
    expect(screen.getAllByLabelText(/Contraseña/i).length).toBe(2);
    expect(screen.getByLabelText(/Confirmar/i)).toBeInTheDocument();
  });

  it("submit → llama onSubmit con FormEvent", () => {
    const onSubmit = vi.fn((e: React.FormEvent) => e.preventDefault());
    renderWithLanguage(<LoginForm {...baseProps({ onSubmit })} />);

    // Encuentra el form por el input de email dentro
    const emailInput = screen.getByLabelText(/Email/i);
    const form = emailInput.closest("form");
    expect(form).toBeInTheDocument();
    fireEvent.submit(form!);

    expect(onSubmit).toHaveBeenCalled();
  });

  it("error prop → renderiza el mensaje de error", () => {
    renderWithLanguage(<LoginForm {...baseProps({ error: "Credenciales inválidas" })} />);

    expect(screen.getByText("Credenciales inválidas")).toBeInTheDocument();
  });

  it("busy=true → submit button disabled", () => {
    renderWithLanguage(<LoginForm {...baseProps({ busy: true })} />);

    // El submit button es el único con type="submit" en el form
    const form = document.querySelector("form");
    const submitBtn = form?.querySelector('button[type="submit"]');
    expect(submitBtn).toBeDisabled();
  });
});
