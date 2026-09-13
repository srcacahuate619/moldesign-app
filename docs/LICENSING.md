# Licenciamiento de MolDesign

Estado vigente desde 2026-09-10. Los textos normativos son `LICENSE`, `LICENSE-MODELS` y `COMMERCIAL-LICENSE.md`; este documento sólo los explica.

| Componente | Términos |
|---|---|
| Código propio | PolyForm Noncommercial 1.0.0 |
| Modelos propios identificados y autorizados | PolyForm Noncommercial 1.0.0, documentada en `LICENSE-MODELS` |
| Uso comercial | Requiere licencia escrita separada; tarifa, regalía o comisión negociada caso por caso |
| Terceros | Conservan íntegramente sus licencias y atribuciones |

MolDesign permite uso académico, educativo, personal, de evaluación e investigación **no comercial**. Es software *source-available*, no “open source” según la definición de la OSI: una licencia que prohíbe usos comerciales no satisface la Open Source Definition.

Las copias que terceros ya hubieran recibido legítimamente bajo AGPL conservan irrevocablemente esa concesión para esos bytes. La licencia actual no revoca derechos ya otorgados; gobierna las versiones publicadas bajo PolyForm.

## Uso comercial

PolyForm Noncommercial no incluye una comisión automática ni convierte por sí sola un uso en licencia comercial. Cualquier uso que no sea “Noncommercial Purpose” según el texto normativo exige un acuerdo firmado por Johan Amezcua. `COMMERCIAL-LICENSE.md` es una invitación a negociar, no una licencia concedida.

Las contribuciones requieren el CLA antes de integrarse para que MolDesign pueda mantener una oferta dual. El historial auditado a 2026-09-10 muestra un único autor, pero este hecho debe volver a comprobarse después de aceptar contribuciones.

## Componentes de terceros

Open Babel 3.1.1.23 es un programa independiente GPL-2.0-only, ejecutado por subproceso y agregado al instalador con su propia licencia, procedencia y fuente correspondiente/oferta efectiva. Su inclusión no convierte su código en PolyForm ni autoriza importar sus bindings dentro de MolDesign.

Las licencias permisivas, LGPL, GPL y licencias específicas de modelos conservan sus condiciones. `frontend/public/legal/THIRD_PARTY_NOTICES.md` es el índice operativo; no sustituye los textos completos.

## Modelos y datos

El repositorio y el instalador sólo pueden incluir un peso cuando su manifiesto identifica simultáneamente:

1. autor/titular del modelo;
2. licencia del código y del peso;
3. datasets y versión usados;
4. derecho verificable para distribuir el peso resultante; y
5. hash del artefacto exacto.

ESMFold y los LLM pesados se descargan bajo demanda y mantienen las licencias de sus autores. “Descargable” no significa que MolDesign pueda relicenciarlos.

La capacidad de relicenciar código propio no concede derechos sobre datasets de terceros. El registro Zenodo 7014096 usado para PDBbind v2020 no muestra licencia en `Rights`, y una fuente académica reciente documenta que PDBbind prohíbe redistribuir sin permiso explícito. Por ello, datos y pesos derivados se encuentran en `REVIEW_REQUIRED` hasta obtener permiso escrito o ser sustituidos mediante reentrenamiento de procedencia limpia. Ver `docs/86_AUDITORIA_LEGAL_RELEASE_PUBLICO_Y_STORE.md`.

## Microsoft Store

La distribución mediante Microsoft Store es un canal adicional, no una licencia nueva sobre MolDesign. Partner Center debe incluir una URL a la licencia PolyForm en “Additional license terms”; dejarla vacía aplicaría los Standard Application License Terms de Microsoft a los clientes. También debe proporcionarse la política pública `PRIVACY.md`.

Este documento no sustituye asesoría jurídica profesional.
