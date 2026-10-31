import type { EngineState, EngineStatus } from "../context/DownloadProvider";
import type { Translate } from "./frontendError";
const LABEL_KEYS: Record<EngineState, string> = {
  "idle": "c_engine_idle",
  "starting": "c_engine_starting",
  "ready": "c_engine_ready",
  "not_installed": "c_engine_not_installed",
  "spawn_failed": "c_engine_spawn_failed",
  "health_failed": "c_engine_health_failed",
  "disconnected": "c_engine_disconnected"
};
const EXPLANATION_KEYS: Partial<Record<EngineState, string>> = {
  "not_installed": "c_engine_explain_not_installed",
  "spawn_failed": "c_engine_explain_spawn_failed",
  "health_failed": "c_engine_explain_health_failed",
  "disconnected": "c_engine_explain_disconnected"
};
export const engineStateLabel = (state: EngineState, t: Translate): string => t(LABEL_KEYS[state]);
export const engineExplanation = (state: EngineState, t: Translate): string | null => EXPLANATION_KEYS[state] ? t(EXPLANATION_KEYS[state]!) : null;
export const engineStatusDetail = (engine: EngineStatus, t: Translate): string | null => engine.detailMessage ? engine.detailMessage.render(t) : engine.detail;
