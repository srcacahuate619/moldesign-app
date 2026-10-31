import { ApiError } from "./api";
export function saveFailureKind(error: unknown): "session" | "missing" | "other" {
  if (error instanceof ApiError && (error.status === 401 || error.status === 403)) return "session";
  if (error instanceof ApiError && error.status === 404) return "missing";
  return "other";
}
