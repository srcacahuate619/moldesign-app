import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { sortCaseEntries } from "../../../lib/cases/repository";
import type { CaseIndexEntry } from "../../../lib/cases/types";
import { CaseSidebar } from "../CaseSidebar";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function caseEntry(
  id: string,
  createdAt: string,
  overrides: Partial<CaseIndexEntry> = {},
): CaseIndexEntry {
  return {
    id,
    name: id,
    status: "review",
    createdAt,
    updatedAt: createdAt,
    lastOpenedAt: createdAt,
    archived: false,
    storageMode: "browser",
    ...overrides,
  };
}

function props(cases: readonly CaseIndexEntry[]) {
  return {
    cases,
    activeCaseId: null,
    loading: false,
    onSelect: vi.fn(),
    onCreate: vi.fn(),
    onArchive: vi.fn(),
    onRecover: vi.fn(),
    canReveal: false,
    workLocked: false,
  };
}

describe("CaseSidebar", () => {
  it("muestra tiempo desde la última evaluación, no desde la última apertura", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-26T12:00:00.000Z"));
    const evaluated = caseEntry("Caso evaluado", "2026-08-01T10:00:00.000Z", {
      lastOpenedAt: "2026-08-26T11:59:59.000Z",
      activeRun: {
        taskId: "run-1",
        executionState: "completed",
        startedAt: "2026-08-26T10:00:00.000Z",
      },
    });

    render(<CaseSidebar {...props([evaluated])} />);

    expect(screen.getByText(/en revisión · evaluada hace 2 h/i)).toBeInTheDocument();
    expect(screen.queryByText(/hace instantes/i)).not.toBeInTheDocument();
  });

  it("seleccionar sólo cambia el caso activo y no promueve su fila", () => {
    const older = caseEntry("Caso antiguo", "2026-08-01T10:00:00.000Z");
    const newer = caseEntry("Caso nuevo", "2026-08-20T10:00:00.000Z");
    const onSelect = vi.fn();
    const initial = sortCaseEntries([older, newer]);
    const { rerender } = render(
      <CaseSidebar {...props(initial)} onSelect={onSelect} />,
    );

    const oldCaseButton = screen.getByText("Caso antiguo").closest("button");
    expect(oldCaseButton).not.toBeNull();
    fireEvent.click(oldCaseButton as HTMLButtonElement);
    expect(onSelect).toHaveBeenCalledWith("Caso antiguo");

    const reopened = { ...older, lastOpenedAt: "2026-08-26T12:00:00.000Z" };
    rerender(
      <CaseSidebar
        {...props(sortCaseEntries([reopened, newer]))}
        activeCaseId="Caso antiguo"
        onSelect={onSelect}
      />,
    );

    const caseButtons = within(screen.getByRole("navigation", { name: "Casos" }))
      .getAllByRole("button")
      .filter((button) => button.textContent?.includes("Caso "));
    expect(caseButtons.map((button) => button.textContent)).toEqual([
      expect.stringContaining("Caso nuevo"),
      expect.stringContaining("Caso antiguo"),
    ]);
    expect(screen.getByText("Caso antiguo").closest("button")).toHaveAttribute("aria-current", "page");
  });

  it("declara cuando un caso todavía no tiene evaluaciones", () => {
    render(<CaseSidebar {...props([caseEntry("Caso vacío", "2026-08-20T10:00:00.000Z")])} />);
    expect(screen.getByText(/en revisión · sin evaluaciones/i)).toBeInTheDocument();
  });
});
