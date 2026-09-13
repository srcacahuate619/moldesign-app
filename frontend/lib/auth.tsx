"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

type User = {
  user_id: string;
  username: string;
  email: string;
};

type AuthContextType = {
  user: User | null;
  token: string | null;
  refreshToken: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  loginWithOAuth: (provider: string, id_token: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextType | null>(null);

import { getApiUrl } from "./config";
import { recordarInvitado } from "./traspaso";

/**
 * Detecta si el frontend corre dentro del runtime Tauri (escritorio).
 * Tauri v2 inyecta `window.__TAURI_INTERNALS__` en el WebView de forma
 * automática; `window.__TAURI__` solo con `withGlobalTauri`. Usar la
 * detección por runtime evita depender de rebuilds o env vars al arrancar
 * con `npx tauri dev`.
 */
function isDesktopRuntime(): boolean {
  if (typeof window === "undefined") return false;
  return "__TAURI_INTERNALS__" in window || "__TAURI__" in window;
}

/**
 * Extrae un mensaje de error legible del response HTTP.
 * FastAPI/Pydantic puede devolver `detail` como:
 *   - string:  "Ese nombre de usuario ya está en uso"  → se usa directo
 *   - list:    [{loc, msg}, ...] (errores de validación 422) → se unen los msg
 *   - dict/object: puede ser un objeto anidado → se serializa
 *   - ausente:  → "HTTP <status>"
 * Sin esto, `new Error(lista)` produce "[object Object]" en la UI.
 */
async function extractErrorDetail(res: Response): Promise<string> {
  const status = res.status;
  let data: any = {};
  try {
    data = await res.json();
  } catch {
    return `HTTP ${status}`;
  }
  const detail = data?.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail)) {
    // Errores de validación Pydantic: [{"loc": [...], "msg": "..."}]
    const msgs = detail
      .map((d: any) => (d && typeof d.msg === "string" ? translateValidationMsg(d) : null))
      .filter(Boolean);
    if (msgs.length) return msgs.join("; ");
    return `HTTP ${status}`;
  }
  if (detail && typeof detail === "object") {
    // Objeto de error (ej. {"detail": {"message": "..."}})
    // El detalle viene del backend y su forma no está en ningún contrato: se
    // tipa como registro de valores desconocidos, que obliga a comprobar antes
    // de usar. `as any` dejaba pasar `msg.trim()` sobre cualquier cosa.
    const posible = detail as Record<string, unknown>;
    const msg = posible.message ?? posible.msg ?? posible.error;
    if (typeof msg === "string" && msg.trim()) return msg;
    try {
      return JSON.stringify(detail);
    } catch {
      return `HTTP ${status}`;
    }
  }
  return `HTTP ${status}`;
}

/** Traduce mensajes de validación Pydantic comunes a un español legible. */
function translateValidationMsg(d: any): string {
  const raw = d.msg || "";
  const field = Array.isArray(d.loc) ? String(d.loc[d.loc.length - 1] ?? "") : "";
  const fieldLabel = field === "password" ? "contraseña" : field === "username" ? "nombre de usuario" : field === "email" ? "email" : field;
  if (/at least 8 characters/i.test(raw)) return `La ${fieldLabel} debe tener al menos 8 caracteres.`;
  if (/at least 3 characters/i.test(raw)) return `El ${fieldLabel} debe tener al menos 3 caracteres.`;
  if (/should not be empty|may not be empty/i.test(raw)) return `El campo ${fieldLabel} no puede estar vacío.`;
  if (/not a valid email/i.test(raw)) return `El email no es válido.`;
  if (/should be a valid email/i.test(raw)) return `El email no es válido.`;
  return raw;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Restore from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem("moldesign_auth");
    if (stored) {
      try {
        const data = JSON.parse(stored);
        setToken(data.token);
        setRefreshToken(data.refreshToken);
        setUser(data.user);
        setIsLoading(false);
      } catch {
        localStorage.removeItem("moldesign_auth");
        setIsLoading(false);
      }
    } else if (isDesktopRuntime()) {
      // Modo DESKTOP: auto-login con el usuario local del backend
      // (GET /auth/desktop-login). Sin esto, Tauri mostraba el login manual
      // aunque la app de escritorio ya tiene un usuario pre-configurado.
      // `getApiUrl()` es una promesa —en escritorio el puerto lo elige Rust—
      // y este efecto no es asíncrono, así que la cadena arranca desde ella.
      getApiUrl()
        .then((base) =>
          fetch(`${base}/auth/desktop-login`, {
            headers: { "ngrok-skip-browser-warning": "true" },
            cache: "no-store",
          }),
        )
        .then(async (res) => {
          if (!res.ok) throw new Error(`desktop-login ${res.status}`);
          const data = await res.json();
          if (data?.access_token) {
            // Esta —y sólo esta— es la puerta por la que se entra como invitado.
            // Se recuerda aquí porque `_persist` sobrescribe `moldesign_auth` y
            // la identidad del invitado desaparecía justo en el acto que la
            // necesita: registrarse. No se deduce del email ni del nombre.
            recordarInvitado({
              user_id: data.user_id,
              username: data.username,
              email: data.email,
            });
            _persist(data.access_token, data.refresh_token, {
              user_id: data.user_id,
              username: data.username,
              email: data.email,
            });
          }
        })
        .catch((err) => console.warn("[Auth] Desktop auto-login falló:", err))
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }

    // Escuchar el evento de expiración desde api.ts
    const handleAuthExpired = () => {
      setToken(null);
      setRefreshToken(null);
      setUser(null);
      localStorage.removeItem("moldesign_auth");
    };
    window.addEventListener('auth_expired', handleAuthExpired);
    return () => window.removeEventListener('auth_expired', handleAuthExpired);
  }, []);

  const _persist = useCallback((tok: string, refTok: string, u: User) => {
    setToken(tok);
    setRefreshToken(refTok);
    setUser(u);
    localStorage.setItem(
      "moldesign_auth",
      JSON.stringify({ token: tok, refreshToken: refTok, user: u })
    );
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await fetch(`${await getApiUrl()}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        throw new Error(await extractErrorDetail(res));
      }
      const data = await res.json();
      _persist(data.access_token, data.refresh_token, {
        user_id: data.user_id,
        username: data.username,
        email: data.email,
      });
    },
    [_persist]
  );

  const register = useCallback(
    async (email: string, username: string, password: string) => {
      const res = await fetch(`${await getApiUrl()}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, username, password }),
      });
      if (!res.ok) {
        throw new Error(await extractErrorDetail(res));
      }
      const data = await res.json();
      _persist(data.access_token, data.refresh_token, {
        user_id: data.user_id,
        username: data.username,
        email: data.email,
      });
    },
    [_persist]
  );

  const loginWithOAuth = useCallback(
    async (provider: string, id_token: string) => {
      const res = await fetch(`${await getApiUrl()}/auth/oauth`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider, id_token }),
      });
      if (!res.ok) {
        if (res.status === 403) {
            throw new Error("Debe registrarse primero para usar esta cuenta.");
        }
        throw new Error(await extractErrorDetail(res));
      }
      const data = await res.json();
      _persist(data.access_token, data.refresh_token, {
        user_id: data.user_id,
        username: data.username,
        email: data.email,
      });
    },
    [_persist]
  );

  const logout = useCallback(() => {
    setToken(null);
    setRefreshToken(null);
    setUser(null);
    localStorage.removeItem("moldesign_auth");
  }, []);

  const value = useMemo(
    () => ({ user, token, refreshToken, isLoading, login, register, loginWithOAuth, logout }),
    [user, token, refreshToken, isLoading, login, register, loginWithOAuth, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
