import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
const language = vi.hoisted(() => ({ locale: "es" as "es" | "en" }));
vi.mock("@/context/LanguageContext", async importOriginal => {
  const actual = await importOriginal<typeof import("@/context/LanguageContext")>();
  return { ...actual, useLanguage: () => ({ t: (key: string) => actual.TRANSLATIONS[language.locale][key] ?? key }) };
});
import { CaseContextPanel } from "../CaseContextPanel";
afterEach(() => { cleanup(); language.locale = "es"; });
describe("contexto del caso en el idioma elegido", () => {
  it("traduce las siete preguntas y conserva el texto y el campo al cambiar de idioma", () => {
    const onChange = vi.fn();
    const view = render(<CaseContextPanel context={{question:"Hipótesis propia"}} saveState="idle" onChange={onChange} embedded />);
    expect(screen.getByLabelText("¿Qué intenta responder este caso?")).toHaveValue("Hipótesis propia");
    language.locale = "en";
    view.rerender(<CaseContextPanel context={{question:"Hipótesis propia"}} saveState="idle" onChange={onChange} embedded />);
    const questions = ["What question does this case address?", "What decision will be made?", "What justifies the choice of system?", "What controls or references are available?", "What assumptions are being made?", "What uncertainties are already known?", "Notes"];
    for (const question of questions) expect(screen.getByLabelText(question)).toBeInTheDocument();
    expect(screen.getByText("Without this, the dossier cannot state what question was being asked.")).toBeInTheDocument();
    expect(screen.queryByText("¿Qué intenta responder este caso?")).toBeNull();
    fireEvent.change(screen.getByLabelText(questions[0]), {target:{value:"New hypothesis"}});
    expect(onChange).toHaveBeenCalledWith({question:"New hypothesis"});
  });
});
