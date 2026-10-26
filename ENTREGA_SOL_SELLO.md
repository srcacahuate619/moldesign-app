# Entrega del sello del catálogo — MolDesign 1.0.2

> **Nota de reubicación (2026-10-11).** El worktree `catalogo-demostracion` se retiró el 2026-10-11. La rama `sol/catalogo-sello` sigue existiendo. Índice: [REUBICACIONES_2026-10-11.md](docs/REUBICACIONES_2026-10-11.md).

Fecha: 2026-10-09. Rama: `sol/catalogo-sello`. Base: `e9b032ae` de
`codex/release-hygiene`. Worktree:
`D:\moldesign-build\.worktrees\catalogo-demostracion`.

Los cinco puntos del encargo están implementados en el frontend. El sello
declara las cifras, la pose, los parámetros y todas las condiciones; las listas
usan su variante compacta. Preparación prefiere el PDB explícito de la corrida.
El backend y el registro real de verificados no se modificaron.

## Commits y archivos

Las rutas de esta lista son relativas a la raíz del worktree. Cada uno de los
cinco commits incluye su fila en `docs/versions/1.0.2_cambios.md`, sin separar
la tabla con líneas en blanco.

1. **2.1 — `b149b9a4`: Exige el protocolo y las condiciones del sello en el frontend.**
   - `frontend/lib/seccionCatalogo.ts`
   - `frontend/lib/__tests__/seccionCatalogo.test.ts`
   - `frontend/lib/__tests__/fixtures/verificacionReceptor.ts`
   - `frontend/components/science/__tests__/InsigniaDemostracion.test.tsx`
   - `frontend/components/interfaces/pro/__tests__/TargetSelectorModal.render.test.tsx`
   - `docs/versions/1.0.2_cambios.md`
2. **2.2 — `62b1ebb8`: Muestra el sello y el alcance de su calibración en los resultados.**
   - `frontend/components/science/InsigniaDelCatalogo.tsx`
   - `frontend/components/science/InsigniaDemostracion.tsx`
   - `frontend/components/science/__tests__/InsigniaDelCatalogo.test.tsx`
   - `frontend/components/science/__tests__/InsigniaDemostracion.test.tsx`
   - `frontend/lib/seccionCatalogo.ts`
   - `frontend/context/traducciones/catalogo.ts`
   - `frontend/components/interfaces/pro/ProEvaluation.tsx`
   - `frontend/components/interfaces/pro/EvaluationEvidencePanel.tsx`
   - `frontend/components/cases/CaseRunHistoryModal.tsx`
   - `frontend/components/evaluation/BatchRowResult.tsx`
   - `frontend/components/MoldexCard.tsx`
   - `frontend/app/evaluation/batch/page.tsx`
   - `frontend/app/preparacion/page.tsx`
   - `frontend/app/moldex/page.tsx`
   - `frontend/app/molcy/page.tsx`
   - `docs/versions/1.0.2_cambios.md`
3. **2.3 — `3f224b26`: Compacta las insignias de las listas y conserva su explicación.**
   - `frontend/components/science/InsigniaDelCatalogo.tsx`
   - `frontend/components/science/__tests__/InsigniaDelCatalogo.test.tsx`
   - `frontend/components/science/__tests__/ListasDelCatalogo.test.tsx`
   - `frontend/components/MoldexCard.tsx`
   - `frontend/components/evaluation/BatchRowResult.tsx`
   - `frontend/app/evaluation/batch/page.tsx`
   - `docs/versions/1.0.2_cambios.md`
4. **2.4 — `67f7bfc3`: Evita repetir la sección en las tarjetas del selector.**
   - `frontend/components/science/SeccionDelCatalogo.tsx`
   - `frontend/components/molcy/CatalogoReceptoresMolcy.tsx`
   - `frontend/components/interfaces/pro/__tests__/TargetSelectorModal.render.test.tsx`
   - `frontend/components/molcy/__tests__/CatalogoReceptoresMolcy.test.tsx`
   - `docs/versions/1.0.2_cambios.md`
5. **2.5 — `a7b98393`: Identifica el receptor de Preparación por el PDB de la corrida.**
   - `frontend/lib/preparacion.ts`
   - `frontend/app/preparacion/page.tsx`
   - `frontend/app/preparacion/__tests__/pdbDelCatalogo.test.tsx`
   - `docs/versions/1.0.2_cambios.md`

El commit final de documentación añade este archivo, las capturas y sus
comprobaciones en `docs/capturas/sello-20261009/`, los registros de ejecución
en `docs/verificacion/sello-20261009/` y su fila en el registro de cambios.
Su hash se obtiene con `git log -1 --format="%h %s" -- ENTREGA_SOL_SELLO.md`:
un archivo no puede incluir el hash del commit que lo contiene.

## Pruebas y resultados

Comandos ejecutados desde `frontend/` del worktree, con las dependencias de la
rama principal mediante junction. Para Vitest, `TEMP` y `TMP` apuntaron a
`frontend/.tmp`; se limitaron los workers a dos. No se modificó la configuración
de pruebas ni se añadieron excepciones a los guardianes.

| Comando | Resultado |
|---|---|
| `npm run test:run -- --maxWorkers=2` | **1694/1694**, 182 archivos, salida 0; 289,50 s. Incluye idiomas y guardián de textos pendientes. |
| `npx tsc --noEmit` | Salida 0, sin diagnósticos. Repetido al cerrar después de retirar el arnés temporal. |
| `npm run lint` | Salida 0; **0 errores y 39 advertencias**, el mismo conteo de la entrega anterior. |
| `git diff --check` | Sin defectos de espacios. |

Los registros íntegros de la suite y lint y el resultado de TypeScript están
en `docs/verificacion/sello-20261009/`. Respecto a los 1658 tests de la base,
la suite incorpora **36 pruebas** y tres archivos de pruebas nuevos.

Cobertura añadida y ampliada:

- **Contrato:** ausencia de protocolo o condiciones, condiciones vacías válidas,
  campos incompletos y criterios negativos del protocolo; privados y comunidad
  siguen fuera del sello. Una prueba contrasta por lectura la receta 7 con
  `backend/services/docking/preparer.py`.
- **Sello:** cifras, pose, parámetros y las tres condiciones en español e inglés;
  formato de rho e intervalo a dos decimales y RMSD a uno; código desconocido
  visible, incluido `constructor` para evitar ocultarlo por claves heredadas.
- **Corrida:** parámetros iguales, distintos, ausentes o nulos; cada campo presente
  cuenta, incluso semillas contradictorias entre `docking_protocol.seed` y
  `vina_random_seed`. No se sustituye un dato ausente por la configuración actual.
- **Listas:** etiqueta visible compacta y explicación íntegra en `aria-label` y
  `title` en ambos idiomas. Pruebas sobre `MoldexCard` y `BatchRowResult` reales;
  el resultado expandido conserva el sello y la advertencia por parámetros distintos.
- **Selectores:** búsqueda con los tres encabezados, tarjeta de demostración sin
  etiqueta redundante y con sus avisos y respaldo. Molcy conserva disponibilidad,
  selección y subida; una entrada ficticia muestra su sello al buscarla.
- **Preparación:** `corrida.pdb_id` gana a un rótulo contradictorio; sin el campo
  se usa `PDB · nombre`. Ambas pruebas montan la página y conservan BLOQUEADO.
- **Registro vacío:** siguen pasando las pruebas de catálogo antiguo, estado vacío,
  selección de demostración, propios, comunidad, caché e historial.

Comprobaciones por punto: 2.1, 38 pruebas en tres archivos; 2.2, 49 en cinco;
2.3, 64 en cuatro; 2.4, 37 en tres; 2.5, 23 en tres. Son conjuntos solapados,
no se suman al conteo de la suite completa.

## Capturas y alcance comprobado

Se montaron los componentes reales, las traducciones y el CSS del proyecto en
un arnés local de Vite. La entrada ficticia del encargo se inyectó por prop al
sello y en el hook del catálogo usado por la ficha real de Moldex, sólo dentro
del arnés. No se escribió en ningún JSON real ni se arrancó el backend.
Cada captura declara de forma visible que las cifras no representan una
calibración de 8HFI. La molécula de la fila también es ficticia y no tiene imagen
ni índice medidos.

- `docs/capturas/sello-20261009/sello-es.png`: sello y Moldex en español.
- `docs/capturas/sello-20261009/sello-en.png`: los mismos componentes en inglés.
- `docs/capturas/sello-20261009/moldex-compacta-es.png`: fila compacta de 360 px.
- `docs/capturas/sello-20261009/sello-en-375.png`: inglés a 375 px.
- `docs/capturas/sello-20261009/comprobaciones.json`: ocho combinaciones de
  idioma (es/en), tema (dark/light) y ancho (1440/375). Sin errores de página,
  sin desbordamiento horizontal y con la insignia dentro de la fila. Texto
  compacto, atributos completos y cifras comprobados. Capturas inspeccionadas.

Se corrigieron dos problemas del arnés antes de conservar las capturas: Tailwind
necesitaba incluir su fuente temporal para generar la distribución de escritorio;
Edge headless omitió caracteres al rasterizar una captura inglesa, aunque el DOM
estaba completo. Se repitió en proceso separado con opciones de rasterización
de fuentes y se inspeccionó de nuevo. No se alteraron los estilos del producto.
El arnés, su cache y el servidor local se retiraron al terminar.

## Decisiones y diferencias con el encargo

1. **Autoridad del backend:** además de los dos campos nuevos, se exige la receta,
   el hash no vacío, las semillas y PoseBusters, rho e intervalo, n, panel y endpoint
   según `supera_el_protocolo`. El frontend es algo más estricto con números no
   finitos y con tipos de panel/endpoint; nunca más permisivo. No pretende verificar
   el contenido científico ni recalcular hashes.
2. **Nombre del componente:** se migraron todos los consumidores al nombre
   `InsigniaDelCatalogo`; `InsigniaDemostracion` conserva un alias por compatibilidad.
   El selector comparte `SelloVerificado`, evitando una segunda presentación de
   parámetros y condiciones.
3. **RMSD por semilla:** se añadió una frase bilingüe que muestra el array opcional
   recibido, con un decimal. No calcula RMSD ni cambia el criterio de pose. Si no
   hay array, la frase no aparece.
4. **Parámetros disponibles:** evaluación, panel e historial usan el resultado de
   la corrida; Moldex usa su procedencia; la cabecera de lote usa `effective_config`.
   La fila de lote compara cuando se recupera su snapshot. El historial resumido
   de lotes, la auditoría de Preparación y las fuentes de Molcy no declaran esos
   parámetros en sus contratos actuales: muestran los del sello sin inventar una
   discrepancia. No fue necesario modificar esos contratos del backend.
5. **Búsqueda:** se comprobó que el selector compartido y el de Molcy conservan los
   encabezados al filtrar. Se retiró únicamente la etiqueta de demostración de
   sus tarjetas; se mantienen los avisos de unidad biológica y los controles y
   detalles existentes.
6. **PDB de Preparación:** el backend de la base ya incorpora el campo anunciado;
   no hubo que esperarlo ni modificarlo. Se añadió como opcional en el tipo del
   frontend para conservar respuestas antiguas y el respaldo existente por caso.
7. **Guía de interfaz:** se aplicó `ui-ux-pro-max` para etiquetas compactas, revelado
   accesible y texto largo. La consulta específica de Next.js no devolvió una
   regla adicional; se usaron los criterios generales. No se instalaron paquetes.
8. **Tabla del registro:** la base todavía tenía una línea en blanco entre las
   filas de `16f29f6` y CPU Molcy (línea 848 de la base). Se retiró en la entrega
   para que el apéndice sea una tabla continua. Las cinco filas nuevas se cerraron
   con sus hashes; sólo el commit que contiene esta entrega queda como «este commit».

Durante las pruebas se corrigieron dos expectativas equivocadas: una buscaba
que no hubiera ningún texto «Demostración» en la sección, pero debía conservarse
su encabezado; otra esperaba la razón cruda del backend en Preparación, cuya
interfaz ya traduce la explicación por estado. La comprobación final usa el
encabezado BLOQUEADO sin cambiar ese comportamiento. La lectura de la receta
en la prueba se hace con una ruta de filesystem; usar `new URL` disparaba la
transformación de assets de Vite sobre el archivo fuera del frontend.

## Lo que queda fuera de esta verificación

Las capturas y las pruebas no prueban una instalación Tauri ni un resultado
científico. No se ejecutaron `tauri:build`, `stage:desktop` ni `smoke:prod`, por
instrucción del encargo; esa comprobación corresponde a Claude. Tampoco se
ejecutaron pruebas del backend, porque no se cambió ningún archivo suyo.
El registro real sigue vacío: no se promocionó 8HFI ni otro receptor. La base
ya documenta el NO_GO de CAL-8HFI-01; las cifras ficticias del sello no sustituyen
esa medida.

No se tocó el árbol principal ni se hizo push, fusión o rebase. Los artefactos
sellados, el motor Molcy, la CSP y los guardianes de build permanecen intactos.
La junction de `frontend/node_modules` se retiró con `rmdir` sobre su ruta literal,
tras comprobar su destino; las dependencias del árbol principal se conservaron.
La rama queda lista para la revisión de Claude.
