import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CustomReceptorModal } from "../CustomReceptorModal";

const upload = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", () => ({ uploadCustomTarget: upload }));
vi.mock("@/context/LanguageContext", () => ({ useLanguage: () => ({ t: (key: string) => key }) }));
beforeEach(() => { upload.mockReset(); upload.mockResolvedValue({}); });

describe("la subida existente también recibe anti-dianas", () => {
  it.each([false, true])("envía la marca sólo al subir una anti-diana: %s", async (antiDiana) => {
    const success = vi.fn();
    const view = render(<CustomReceptorModal antiDiana={antiDiana} onClose={() => {}} onSuccess={success} />);
    fireEvent.change(screen.getByPlaceholderText("pr_custom_name_placeholder"), { target: { value: "Receptor del equipo" } });
    fireEvent.change(view.container.querySelector('input[type="file"]')!, { target: { files: [new File(["ATOM\n"], "equipo.pdb", { type: "text/plain" })] } });
    fireEvent.submit(view.container.querySelector("form")!);
    await waitFor(() => expect(success).toHaveBeenCalledTimes(1));
    const data = upload.mock.calls[0][0] as FormData;
    expect(data.get("is_anti_target")).toBe(antiDiana ? "true" : null);
    expect(data.get("name")).toBe("Receptor del equipo");
    expect((data.get("file") as File).name).toBe("equipo.pdb");
    expect(data.get("chain_id")).toBe("A");
  });
});
