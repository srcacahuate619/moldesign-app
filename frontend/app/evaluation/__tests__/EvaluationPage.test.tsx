import React, { useState } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const authState = vi.hoisted(() => ({
  isLoading: false,
  user: null as { user_id: string } | null,
}));
const replace = vi.hoisted(() => vi.fn());

vi.mock("../../../lib/auth", () => ({ useAuth: () => authState }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
vi.mock("../../../components/cases/CaseWorkspace", () => ({
  CaseWorkspace: () => <div>workspace</div>,
}));
vi.mock("../../../context/CaseContext", () => ({
  CaseProvider: ({ ownerUserId, children }: { ownerUserId: string; children: React.ReactNode }) => {
    const [mountedFor] = useState(ownerUserId);
    return <div data-testid="case-provider" data-owner={ownerUserId} data-mounted-for={mountedFor}>{children}</div>;
  },
}));

import EvaluationPage from "../page";

describe("EvaluationPage — frontera de sesión", () => {
  beforeEach(() => {
    authState.isLoading = false;
    authState.user = null;
    replace.mockClear();
  });

  it("no monta casos mientras la sesión todavía se está restaurando", () => {
    authState.isLoading = true;
    render(<EvaluationPage />);

    expect(screen.getByText(/cargando sesión/i)).toBeInTheDocument();
    expect(screen.queryByTestId("case-provider")).not.toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("sin cuenta redirige al login y nunca abre el repositorio", async () => {
    render(<EvaluationPage />);

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login?returnTo=%2Fevaluation"));
    expect(screen.queryByTestId("case-provider")).not.toBeInTheDocument();
  });

  it("inyecta el user_id autenticado como propietario del workspace", () => {
    authState.user = { user_id: "alice" };
    render(<EvaluationPage />);

    expect(screen.getByTestId("case-provider")).toHaveAttribute("data-owner", "alice");
    expect(screen.getByText("workspace")).toBeInTheDocument();
  });

  it("al cambiar de cuenta remonta el proveedor y no conserva el workspace anterior", () => {
    authState.user = { user_id: "alice" };
    const { rerender } = render(<EvaluationPage />);
    expect(screen.getByTestId("case-provider")).toHaveAttribute("data-mounted-for", "alice");

    authState.user = { user_id: "bob" };
    rerender(<EvaluationPage />);

    const provider = screen.getByTestId("case-provider");
    expect(provider).toHaveAttribute("data-owner", "bob");
    expect(provider).toHaveAttribute("data-mounted-for", "bob");
  });
});
