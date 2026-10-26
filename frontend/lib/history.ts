import { requestAuthenticatedJson } from "./api";

/** El recibo está ligado al task_id; una nueva evaluación no lo sustituye. */
export async function downloadRunReceipt(taskId: string): Promise<void> {
  const data = await requestAuthenticatedJson<{ filename: string; pdf_base64: string }>(
    `/history/receipts/${encodeURIComponent(taskId)}`,
  );
  const bytes = Uint8Array.from(atob(data.pdf_base64), (character) => character.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
  try {
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = data.filename;
    anchor.click();
  } finally {
    URL.revokeObjectURL(url);
  }
}
