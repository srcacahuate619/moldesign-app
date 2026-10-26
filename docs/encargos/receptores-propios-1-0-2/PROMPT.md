# Encargo: receptores propios para MolDesign 1.0.2 (arreglar, no quitar)

Eres una sesión de Claude Code en la máquina del propietario, con el repositorio
`D:\moldesign-build`. Antes de tocar nada, lee **`AGENTS.md`** y
**`D:\moldesign-build\docs\encargos\receptores-propios-1-0-2\CONTEXTO.md`**: el estado
medido, el mapa del código, lo que hay en el runtime, el corpus y los invariantes están
allí, y este prompt no los repite. Esa carpeta **no está commiteada**: vive sólo en el
árbol principal y no aparecerá dentro de tu worktree, así que léela por su ruta
absoluta.

## Objetivo

1.0.2 sale con la sección «Tus receptores» como el camino para decisiones reales, y la
subida de receptores propios tiene defectos medidos: un PDBQT sube «con éxito» y no se
puede evaluar, mmCIF se rechaza, `.PDB` en mayúsculas se rechaza con un mensaje que
esconde el motivo, y el modo automático tira la preparación del usuario. La orden del
propietario es **ARREGLAR, NO QUITAR** ningún modo, y que entre en 1.0.2.

Hay tres caminos, según lo que trae el investigador:

### A. Estructura cruda, experimental o predicha: MolDesign la prepara y la audita

- **mmCIF/PDBx** (`.cif`, `.mmcif`, también en `.gz`): la prioridad. Usa gemmi 0.7.5,
  que ya está en el runtime. Cadenas por `auth_asym_id`, primer modelo, la misma política
  de altlocs que en PDB. Si el archivo declara ensamblajes, decide y **declara** cuál se
  usa. Las cadenas de varias letras y los códigos CCD de 5 caracteres no se truncan ni
  se funden: si el pipeline necesita PDB clásico internamente, usa una correspondencia
  explícita (registrada en el informe de preparación y visible en el dossier con los
  identificadores originales). Si algo no se puede representar, abstente con un motivo.
- **Estructuras predichas** (AlphaFold DB/ModelCIF, AlphaFold 3, Boltz, Chai): lee la
  confianza por residuo (pLDDT) **con la convención verificada en archivos reales** de
  cada fuente, no supuesta. Si los residuos del sitio caen en una zona poco fiable
  (pLDDT < 70), Preparación lo dice con un requisito nuevo que pide revisión y **no
  bloquea**; en estructuras experimentales es NO_APLICA. Si no consigues un archivo real
  de alguna fuente, no afirmes su convención: decláralo.
- **Lo básico**: extensiones sin distinguir mayúsculas (`.pdb`, `.ent`, `.cif`, `.mmcif`,
  `.pqr`, `.pdbqt`, más sus `.gz`); descompresión con un límite de tamaño
  descomprimido (protección contra bombas `.gz`); validación del contenido por formato
  (que el contenido corresponda a la extensión) y mensajes de formato que no ofrezcan lo
  que no existe (hoy se menciona SDF).

### B. Receptor ya preparado por el equipo del usuario: MolDesign lo respeta

- Un modo de preparación nuevo que **respeta** lo que trae el archivo:
  - **Protonación**: HID/HIE/HIP, CYX, ASH, GLH y LYN (Meeko 0.7.1 tiene esas
    plantillas); los nombres de CHARMM HSD/HSE/HSP se traducen a HID/HIE/HIP **y se
    declara** la traducción.
  - **Cofactores, metales y aguas** que estén en el archivo: el usuario ya decidió, así
    que no hace falta lista blanca.
  - **Comprueba** con el JSON parametrizado de Meeko (`protonation_templates`:
    `input_resname` frente a `residue_template_key`) que la plantilla aplicada es la que
    el usuario declaró. Si Meeko la cambia, falla con un motivo; no lo dejes pasar.
- Lo que no se puede representar se abstiene con motivo, nunca se adivina: el **Na⁺**
  (en PDBQT, `NA` es un nitrógeno aceptor), CYM, especies sin plantilla.
- **PQR** (salida de PDB2PQR/PROPKA): léelo, conserva nombres y coordenadas, y declara
  que Vina no usa sus cargas.
- Preparación y el dossier dicen que la protonación es **la declarada por el usuario**
  (con su origen), nunca «validada». Lo demás se audita igual que siempre: huecos,
  cadenas truncadas, especies junto al sitio.

### C. PDBQT listo para Vina: se evalúa, y se audita si trae su estructura de origen

- **Sin estructura de origen**: tiene que poder evaluarse. Hoy el preflight bloquea con
  `RECEPTOR_FUENTE_DISPONIBLE` y la preparación intentaría bajar `USR_xxxx` del RCSB. La
  ejecución usa el PDBQT tal cual, con un informe que registra lo que se puede saber
  (hash, cadenas y tipos de átomo) y deja en `null`, con su motivo, lo que no.
  Preparación sigue su contrato: lo imprescindible sin dato bloquea, pero el motivo y la
  acción son explícitos («sin la estructura de origen no se puede saber qué se retiró:
  súbela para auditar»).
- **Con estructura de origen** (opcional en la misma subida): Preparación audita
  completo, calculando el diff de especies, los huecos y las truncadas desde el origen
  hacia el PDBQT. Comprueba que el origen y el PDBQT corresponden al mismo receptor; si
  no, rechaza con motivo.

### En los tres caminos

- Los errores de la subida dicen qué falló y qué hacer, en castellano y en inglés y sin
  rutas del disco. Hoy el router convierte cualquier `ValueError` en un 400 genérico.
- El modal (`CustomReceptorModal.tsx`) presenta los tres caminos con sus extensiones,
  el campo opcional de origen en el camino C y los errores reales. Todos los textos
  van en los dos idiomas, sin nombres de colores y sin las palabras prohibidas
  («validado», «producción», «certificado», «FEP-ready»).

## Orden recomendado

Un commit por punto, para que una entrega parcial ya sirva:

1. **C sin origen**: el camino roto de hoy.
2. **Lo básico**: extensiones, `.gz` y mensajes de error.
3. **mmCIF** experimental, con la paridad 8HFI PDB ↔ mmCIF.
4. **Códigos CCD de 5 caracteres** y cadenas de varias letras.
5. **C con origen.**
6. **B**: respetar la protonación y las especies.
7. **PQR.**
8. **Predichas y pLDDT.**
9. **El modal.**

## Dónde y cómo trabajas

```powershell
git -C D:\moldesign-build worktree add D:\moldesign-build\.worktrees\receptores-propios -b claude/receptores-propios codex/release-hygiene
```

- Copia al worktree los binarios no versionados (están en `.gitignore`):
  `tools\vina\*.exe *.dll *.bin`, `tools\openbabel\bin\` y `tools\xtb\`. Python:
  `D:\moldesign-build\python-embed\python.exe`. `node_modules` mediante junction, que
  se quita **con `rmdir`, nunca con borrado recursivo**.
- **No hagas push. No fusiones** en `codex/release-hygiene`: lo integra Claude tras
  revisarlo. No toques otros worktrees; Sol trabaja en `sol/catalogo-sello`
  (frontend).
- **Un commit por punto**, con sus pruebas y su fila en `docs/versions/1.0.2_cambios.md`
  (CRLF, sin líneas en blanco dentro de la tabla, `(…, este commit)` en vez del hash).
  Si añades pruebas del backend, ejecuta `scripts/report_test_counts.py --write`.
- Escribe los scripts con la herramienta de archivos, no con heredoc (colapsa las `\`
  de Windows).

## Verificación obligatoria

1. **Invariante del catálogo**: el mismo `receptor_sha256` antes y después para 8HFI,
   1C3R, 3F75, 5VA1 y 1HSG (receta 7). Si cambia, para.
2. **Pruebas unitarias por lector y por modo**, cada una con casos que debe detectar y
   casos que no.
3. **Por la API, con Vina real**: el arnés `qa_subida_receptores.py` de la carpeta del
   encargo. **`--raiz` tiene que apuntar a tu worktree**, para que levante tu backend:

   ```powershell
   D:\moldesign-build\python-embed\python.exe D:\moldesign-build\docs\encargos\receptores-propios-1-0-2\qa_subida_receptores.py --raiz D:\moldesign-build\.worktrees\receptores-propios --salida D:\moldesign-audits\receptores-propios-<fecha>\base
   ```

   Hoy cumple 1 de 4 casos por defecto (comprobado el 2026-10-09, sale con código 1), y
   tiene que cumplir 4 de 4. Puedes copiarlo a `scripts/` dentro de tu rama. Extiéndelo
   con el corpus de la sección 5 de `CONTEXTO.md` (archivos y hashes en
   `D:\moldesign-audits\receptores-propios-<fecha>\`; en el repo sólo fixtures pequeñas
   o sintéticas). Para cada caso aceptado: subida → preflight → evaluación → la
   auditoría de Preparación (`build_preparacion` en proceso, como en
   `backend/tests/test_preparacion_auditoria.py`), registrando su estado y los motivos.
4. **Puertas**:
   - suite completa del backend con python-embed (y declara los fallos que ya existían
     en la base, como `test_dossier_en_espanol_no_cambia` en `manifest.json`);
   - frontend: `npm run test:run`, `npx tsc --noEmit` y `npm run lint`;
   - `scripts/generate_goldens.py --check`, `scripts/generate_catalog_availability.py --check`
     y `scripts/validar_sellos.py --check`.
5. **No ejecutes** `tauri:build`, `stage:desktop` ni `smoke:prod`: los ejecuta Claude al
   integrar.

## Cuándo parar y preguntar al propietario

- Si un arreglo exige cambiar el comportamiento de los receptores del catálogo (receta
  7), relajar el contrato de Preparación o tocar la frontera con Open Babel.
- Si un formato o una fuente no se puede soportar con honestidad en 1.0.2: propón
  dejarlo declarado como no soportado, con su motivo, en vez de improvisar.

## Entrega

`ENTREGA_RECEPTORES_PROPIOS.md` en la raíz del worktree, con:

1. los commits y sus archivos;
2. el informe del arnés (antes 1/4, después N/N, con el corpus completo);
3. la prueba de invariancia del catálogo;
4. la salida resumida de cada puerta;
5. lo que no pudiste verificar, dicho sin rodeos;
6. las decisiones que tomaste fuera del encargo.

Una entrega parcial y honesta vale más que una completa con supuestos.
