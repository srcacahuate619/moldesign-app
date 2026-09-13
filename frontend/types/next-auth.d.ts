/**
 * Los campos que este proyecto añade a la sesión de NextAuth.
 *
 * El callback `session` inyecta `id_token` y `provider` para que el frontend
 * pueda presentárselos a FastAPI. Se escribían con `(session as any).id_token`,
 * que apaga la comprobación de TODO lo que venga detrás y además deja el tipo
 * mintiendo: quien lee `session` no ve que esos campos existen.
 *
 * `next-auth` está pensado justo para esto: se aumenta el módulo.
 */
import "next-auth";

declare module "next-auth" {
  interface Session {
    /** `id_token` de OIDC, el que se canjea contra FastAPI. */
    id_token?: string;
    /** Proveedor que emitió el token (`google`, etc.). */
    provider?: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    id_token?: string;
    provider?: string;
  }
}
