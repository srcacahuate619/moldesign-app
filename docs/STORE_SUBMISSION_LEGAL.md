# Ficha jurídica para Microsoft Store (MSIX)

Estado: preparada para completar Partner Center; no sustituye la certificación de Microsoft ni asesoría jurídica.

## Identidad reservada

| Campo del manifiesto | Valor exacto |
|---|---|
| `Package/Identity/Name` | `amezcua-dev.com.MolDesign` |
| `Package/Identity/Publisher` | `CN=6441FBBA-B77A-4619-9CEB-ACEDE74573C0` |
| `Package/Properties/PublisherDisplayName` | `amezcua-dev.com` |

Los valores son sensibles a mayúsculas, espacios y puntuación. El paquete que genere Claude debe conservarlos literalmente.

## Campos de Partner Center

Valores decididos para el **primer envío oficial** (2026-09-12):

| Campo de Partner Center | Valor |
|---|---|
| **Version** | `1.0.0.0` — decidido con `store_build_override: 0`, para que el número que ve el usuario coincida con la versión del producto. Ver `msix/msix-config.json → version_del_store`. |
| **Additional license terms** | `https://github.com/srcacahuate619/moldesign-app/blob/v1.0.0/LICENSE` — no dejar vacío: MolDesign no usa los Standard Application License Terms como licencia principal. |
| **Privacy policy** | `https://molecule-design.amezcua-dev.com/privacy/` — publicar primero `site/privacy/index.html` en Cloudflare Pages y marcar que la app puede transmitir información cuando se activan integraciones externas. |
| **Support contact** | `soporte-moldesign@amezcua-dev.com` |
| **Developed by** | `Johan Amezcua` |
| **Copyright/trademark** | `Copyright © 2026 Johan Amezcua. MolDesign no es una marca registrada declarada.` |
| **Website** | `https://molecule-design.amezcua-dev.com/` — publicar primero `site/index.html` en Cloudflare Pages. |

La URL de licencia sigue apuntando a la etiqueta `v1.0.0`, no a una rama: una URL de rama cambia de contenido bajo los pies del revisor. Las URLs de privacidad y web dependen del despliegue HTTPS en Cloudflare Pages; deben responder sin login, sin backend y con el contenido vigente antes de completar Partner Center.

Sobre el sitio anterior: `https://molecule-design.vercel.app/` anunciaba un servicio web con login que ya no está activo, se quedaba en «CARGANDO DATOS DEL CAMPUS…» y no contenía ni política de privacidad ni términos. **No usarlo en Partner Center.** La nueva superficie pública vive en `site/index.html` y `site/privacy/index.html`; se sirve como HTML estático separado de la aplicación desktop para que el revisor no dependa del backend local ni del login.

La URL del repositorio ya viaja **dentro de la aplicación**, en *Acerca de → Código fuente* (`PRODUCT.sourceUrl` en `frontend/lib/softwareCatalog.ts`).

No afirmar afiliación, certificación ni aprobación por Microsoft, Schrödinger, AutoDock, RCSB PDB, PDBbind, Meta, Prior Labs u otros terceros.

## Firma

Para una entrega **MSIX por Microsoft Store**, Microsoft vuelve a firmar el paquete aprobado y no hace falta comprar un certificado de una CA. Esto no se extiende al `.exe`/`.msi` ni a un MSIX distribuido por descarga directa: esos canales requieren su propia estrategia de firma y confianza.

## Archivos jurídicos que deben viajar

- `LICENSE`, `LICENSE-MODELS`, `COMMERCIAL-LICENSE.md`, `PRIVACY.md` y `CLA.md`.
- `THIRD_PARTY_NOTICES.md` y textos íntegros exigidos por cada dependencia.
- Open Babel: licencia GPL-2.0-only, manifiesto, hashes, oferta/código fuente correspondiente y procedencia.
- Instrucciones de reconstrucción o reemplazo para componentes LGPL cuando resulten aplicables.

## Condiciones antes de enviar

1. PDBbind: **resuelto** por determinación del autor (2026-09-12). Los pesos se distribuyen como obra del autor; las tablas de afinidades derivadas se excluyen del paquete (ver `frontend/public/legal/RELEASE_BLOCKERS.md` y `THIRD_PARTY_NOTICES.md`).
2. Presentar la justificación de `runFullTrust` redactada en `docs/STORE_RUNFULLTRUST_JUSTIFICATION.md`.
3. Publicar URLs estables de licencia, privacidad y soporte.
4. Ejecutar Windows App Certification Kit sobre el MSIX final.
5. Verificar que la lista de dependencias del paquete coincide con `THIRD_PARTY_NOTICES.md`.
6. Probar la instalación y desinstalación en una VM limpia desde el canal de prueba de Store.
