import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { RunDataExplorer, runDataFields } from "../RunDataExplorer";
import { RESULT_FIELD_KEYS } from "@/lib/resultFieldKeys";

describe("consultable run data", () => {
  it("keeps null, false, absent and empty distinct and includes unknown/nested fields", () => {
    const fields = runDataFields({ lipinski_pass: null, is_pains: false, scientific_warnings: [], future: { nested: { metric: 0 } } });
    expect(fields).toHaveLength(RESULT_FIELD_KEYS.length + 1);
    const logical = runDataFields({receptor_path:"runs/receptors/sha/receptor.pdbqt"});
    expect(logical.find(field => field.key === "receptor_path")?.value).toBe("runs/receptors/sha/receptor.pdbqt");
    const separate = runDataFields({a:{file:"D:/first/pose.sdf"}, b:{file:"D:/second/pose.sdf"}});
    expect(separate.find(field => field.key === "a")?.value).not.toEqual(separate.find(field => field.key === "b")?.value);
    expect(fields.find(field => field.key === "lipinski_pass")).toMatchObject({ state: "null", value: null });
    expect(fields.find(field => field.key === "is_pains")).toMatchObject({ state: "recorded", value: false });
    expect(fields.find(field => field.key === "scientific_warnings")).toMatchObject({ state: "recorded", value: [] });
    expect(fields.find(field => field.key === "task_id")).toMatchObject({ state: "absent" });
    render(<RunDataExplorer result={{ future: { nested: { metric: 0 } } }} />);
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "metric" } });
    expect(screen.getByText("future")).toBeVisible();
    fireEvent.click(screen.getByText("future"));
    expect(screen.getByText("0")).toBeVisible();
  });
  it("exports logical file references without exposing local absolute paths", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator,"clipboard",{ configurable: true, value: {writeText} });
    render(<RunDataExplorer result={{ task_id: "run-A", receptor_path: "D:\\private\\receptor.pdbqt", extra: { file: "/private/poses.sdf" } }} />);
    fireEvent.click(screen.getByRole("button", { name: "Copiar datos" }));
    expect(writeText).toHaveBeenCalledOnce();
    const exported = JSON.parse(writeText.mock.calls[0][0]);
    expect(exported.fields.find((field: {key:string}) => field.key === "task_id").value).toBe("run-A");
    expect(writeText.mock.calls[0][0]).not.toMatch(/private|D:\\\\/);
    expect(writeText.mock.calls[0][0]).toContain("receptor.pdbqt");
    expect(writeText.mock.calls[0][0]).toContain("poses.sdf");
    await screen.findByText("Datos copiados.");
  });
});
