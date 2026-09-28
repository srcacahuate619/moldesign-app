# Auditoría de procedencia del catálogo de receptores

> **Numeración.** Se escribió el 2026-09-10 como `87_…` en la rama `codex/legal-catalog`
> y nunca entró en desarrollo; el 87 ya lo ocupaba otro documento. Se integra el
> 2026-09-28 como 91, con el texto original intacto y la actualización del final.

**Fecha:** 10 de septiembre de 2026  
**Alcance:** los 380 receptores declarados en `curated_targets.json`.  
**Naturaleza:** inventario técnico-jurídico interno; no sustituye asesoría legal.

Este documento corrige la presunción demasiado amplia del doc 86: la mera
utilización de un dataset durante el entrenamiento no convierte el peso
resultante en una copia redistribuida del dataset.

## Veredicto

Los **380 receptores pueden mostrarse y distribuirse sin pedir permiso entrada
por entrada**. Sus archivos estructurales proceden del archivo PDB, cuyos datos
se ofrecen bajo CC0 1.0. No son las estructuras preparadas de PDBbind ni quedan
condicionados por la licencia de PDBbind.

La obligación práctica pendiente no es pedir 380 permisos: es conservar una
atribución global a RCSB PDB/wwPDB, mantener el PDB ID visible y atribuir a
UniProt las descripciones funcionales derivadas de UniProtKB.

## Evidencia del origen estructural

- `curated_targets.json` contiene 380 filas y 380 PDB IDs únicos.
- Existe un `.pdb.gz` distribuido para cada uno de esos 380 IDs.
- El script histórico `scripts/descargar_estructuras_catalogo.py` descargó los
  archivos directamente desde `https://files.rcsb.org/download/{PDB_ID}.pdb.gz`.
- Se comparó el contenido descomprimido de los 380 archivos con la descarga
  vigente de RCSB PDB: **376 fueron idénticos byte a byte**.
- Los otros cuatro (`2NNJ`, `4EJJ`, `4NY4`, `5TFT`) conservan idénticos todos
  los registros `ATOM`, `HETATM` y `CONECT`; la copia vigente de RCSB sólo añade
  una revisión de cabecera posterior (`REVDAT`, 12-AUG-26).

Esto permite atribuir de forma trazable los 380 archivos al archivo PDB y
descarta que el catálogo distribuya silenciosamente receptores preparados por
Schrödinger/PDBbind.

## Clasificación por campo

| Campo o contenido | Procedencia | Estado de publicación |
|---|---|---|
| Coordenadas y cabecera `.pdb.gz` | Archivo PDB vía RCSB | Apto, CC0 1.0 |
| PDB ID, título, organismo y resolución obtenidos de RCSB | API/archivo RCSB | Apto, CC0 1.0 |
| Cadena, caja, hotspots, familia y estados de preparación | Curación/cálculo MolDesign | Apto como contenido propio; documentar método |
| Descripciones funcionales en español | Función UniProtKB traducida; fallback al título RCSB | Apto con atribución CC BY 4.0 e indicación de traducción |
| Artículos y textos editoriales del sitio RCSB | No forman parte del archivo/API CC0 | No copiar sin permiso; no se detectaron como fuente del catálogo |

## Cómo se generaron las descripciones

El generador histórico `backend/services/blockchain/target_info.py` seguía esta
ruta explícita:

1. consultaba RCSB Data API para la entrada y sus entidades;
2. seleccionaba una referencia UniProt;
3. tomaba el comentario `FUNCTION` de UniProtKB;
4. eliminaba referencias PubMed entre paréntesis;
5. traducía el resultado al español mediante `deep_translator.GoogleTranslator`;
6. si no encontraba función, usaba el título de la entrada PDB.

Las 380 filas tienen descripción y 368 superan 100 caracteres, por lo que la
atribución de UniProt no debe omitirse. La traducción es una modificación y debe
identificarse como tal conforme a CC BY 4.0.

## Medidas mínimas antes del release

1. Incluir el aviso RCSB PDB/wwPDB (CC0) y UniProt (CC BY 4.0) dentro del
   instalador, el repositorio y la vista de licencias.
2. Presentar las descripciones como «fuente: UniProtKB; traducción/adaptación:
   MolDesign» cuando exista trazabilidad por entrada; mientras no exista ese
   campo, mantener al menos la atribución global.
3. Conservar el PDB ID visible y facilitar la cita de la publicación primaria o
   del DOI de la entrada. Es una recomendación científica de RCSB, no una
   condición adicional de CC0.
4. No atribuir a RCSB ni a UniProt los grids, hotspots o veredictos de MolDesign.

## Fuentes

- RCSB PDB Usage Policy: https://www.rcsb.org/pages/usage-policy
- RCSB PDB citation policy: https://www.rcsb.org/pages/policies
- UniProt license and disclaimer: https://www.uniprot.org/help/license/
- CC0 1.0: https://creativecommons.org/publicdomain/zero/1.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/

## Actualización del 2026-09-28

Medida hoy, con el mismo método (comparación con la descarga vigente de RCSB).

- **El catálogo sigue siendo de 380 receptores**, con 380 PDB ID únicos y un
  `.pdb.gz` para cada uno. Lo que cambió desde el 10 de septiembre son 20
  etiquetas de organismo (`bbab67f` en `codex/audit-rescue`): declaraban
  *Homo sapiens* sobre estructuras de VIH-1, SARS-CoV-2, bacterias, pavo o
  *Torpedo*, y ahora se toman del registro `SOURCE` de cada PDB. Es la misma
  fuente CC0 que la tabla de arriba atribuye a RCSB.
- **`data/targets/` distribuye 65 estructuras más, fuera del catálogo**: el panel
  de anti-dianas de Bowes 2012 (`459a833`), controles y las corridas doradas
  (por ejemplo 3DC3). Esta auditoría no las cubría. Comparadas hoy con RCSB:
  **59 idénticas byte a byte**; las **6** restantes (`8XVK`, `8YUT`, `8ZP2`,
  `9EQG`, `9GJ1`, `9UWL`) no tienen formato PDB en RCSB y se convirtieron desde
  su mmCIF con gemmi (`scripts/bowes44_validar_estructuras.py`), así que son
  derivadas del mismo dato CC0, no copias byte a byte. Detalle por entrada:
  `D:\moldesign-audits\qa-003-producto-1.0.2\procedencia-extras.json`
  (fuera del repositorio).
- **Medidas mínimas del release:** la 1 está hecha. El aviso RCSB PDB/wwPDB (CC0)
  y UniProtKB (CC BY 4.0) vive en `frontend/public/legal/THIRD_PARTY_NOTICES.md`
  y viaja con el instalador; desde esta actualización también nombra las 65
  estructuras de fuera del catálogo. **Sin verificar:** la trazabilidad de la
  descripción UniProt por entrada (medida 2) y la cita de la publicación
  primaria por entrada (medida 3).
