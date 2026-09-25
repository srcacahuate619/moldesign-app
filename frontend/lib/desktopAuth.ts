/** Credencial efímera del backend propio, obtenida sólo por IPC de Tauri. */
import { getApiUrl } from "./config";
import { invoke } from "./tauri";

export interface DesktopLoginPayload {
  access_token: string;
  refresh_token: string;
  user_id: string;
  username: string;
  email: string;
}

export async function desktopLogin(): Promise<DesktopLoginPayload> {
  const base = await getApiUrl();
  const launchToken = await invoke<string>("backend_launch_token");
  if (!launchToken) throw new Error("No se obtuvo el secreto del backend propio");
  const response = await fetch(`${base}/auth/desktop-login`, {
    headers: {
      "X-MolDesign-Launch": launchToken,
      "ngrok-skip-browser-warning": "true",
    },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`desktop-login ${response.status}`);
  return response.json() as Promise<DesktopLoginPayload>;
}
