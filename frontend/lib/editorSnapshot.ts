/** Read-only, per-mounted-editor bridge. No files, timers or polling of Ketcher. */
export type EditorSnapshot = { status: "ok"; molfile: string; revision: string } |
  { status: "not_ready" | "changed" | "too_large" | "read_limit" | "failed" };
export type EditorReader = { snapshot: () => Promise<EditorSnapshot>; check: (revision: string) => boolean };
const readers = new Map<string, EditorReader>();
const listeners = new Map<string, Set<(reader: EditorReader) => void>>();
let nextInstance = 0;
export function createEditorReadBudget(limit: number) {
  let used = 0;
  return { claim: () => { if (used >= limit) return false; used++; return true; } };
}
// Indigo may retain native memory for each export. This limit survives case
// switches and is reset only when the renderer is restarted, not on a timer.
const rendererBudget = createEditorReadBudget(40);
export function claimEditorExport(): boolean { return rendererBudget.claim(); }
export function editorInstanceId(): string { return String(++nextInstance); }
export function registerEditorReader(caseId: string, reader: EditorReader): () => void {
  readers.set(caseId, reader);
  listeners.get(caseId)?.forEach((listener) => listener(reader));
  return () => { if (readers.get(caseId) === reader) readers.delete(caseId); };
}
export function currentEditorReader(caseId: string): EditorReader | undefined { return readers.get(caseId); }
export function waitEditorReader(caseId: string, timeoutMs: number): Promise<EditorReader | undefined> {
  const existing = readers.get(caseId);
  if (existing) return Promise.resolve(existing);
  return new Promise((resolve) => {
    let set = listeners.get(caseId);
    if (!set) { set = new Set(); listeners.set(caseId, set); }
    const listener = (reader: EditorReader) => finish(reader);
    const finish = (reader: EditorReader | undefined) => {
      clearTimeout(timer); set!.delete(listener); if (!set!.size) listeners.delete(caseId); resolve(reader);
    };
    const timer = setTimeout(() => finish(undefined), Math.max(0, timeoutMs));
    set.add(listener);
  });
}
