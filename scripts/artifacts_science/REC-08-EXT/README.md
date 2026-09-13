# REC-08-EXT

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La preparacion del receptor conserva los metales del sitio de union. Perder un ion metalico coordinado al ligando no es documentacion pendiente: es un defecto de produccion, porque el docking se habria hecho contra un bolsillo que no existe.

## Protocolo

Referencia: `Extension de REC-08, mismo metodo y distinta entidad. REC-08 verifico que no se pierden CADENAS del sitio; queda la otra mitad de lo que conto FEP-02 y nadie verifico: 52 complejos con metales en el sitio y mediana de 10 aguas, ninguna documentada. Para cada complejo, con el radio de 8 A que FEP-02 uso para definir sitio: (1) metales y aguas HETATM a <=8 A de algun atomo pesado del ligando en data/pdbbind/<pid>/<pid>_protein.pdb; (2) cuantos sobreviven en data/molflex_train_v2/<pid>/<pid>/rec.pdbqt, emparejados POR COORDENADA con tolerancia 0.5 A y no por numero de residuo, porque la preparacion renumera -REC-08 ya observo que rec.pdbqt tiene mas pares (cadena,resnum) distintos que el PDB de origen-; (3) la diferencia. Metales reconocidos por elemento o nombre de residuo en una lista de 21 especies. Solo lectura.`

## Gate

MEDICION SIN GATES DE DECISION. Cantidades de interes: numero de iones metalicos del sitio perdidos en la preparacion y complejos afectados, con las especies implicadas; y fraccion de aguas del sitio conservadas. LIMITACION DECLARADA ANTES: el emparejamiento es POR COORDENADA con 0.5 A de tolerancia; un atomo desplazado mas de 0.5 A por la preparacion contaria como perdido, de modo que el recuento de perdidas es una COTA SUPERIOR. ASIMETRIA DE INTERPRETACION, declarada tambien antes: perder un metal del sitio es un DEFECTO DE PRODUCCION y obliga a revisar el pipeline; perder aguas es una decision legitima y frecuente, y lo que se reporta de ellas no es un defecto sino que la decision NO ESTA DECLARADA, que es exactamente el hallazgo de FEP-02.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `208967defc9ac7cba2b797677d75084e17105394`, dirty=True

## Estado

- Creado: 2026-08-20T04:53:35.624856+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-20T04:54:45.599570+00:00)
- Finalizado: 2026-08-20T04:54:45.838984+00:00
- Razón de la decisión: DOS RESULTADOS, Y EL IMPORTANTE NO ES EL QUE BUSCABA. (1) METALES: cero perdidas. 29 complejos tienen metal en el sitio, 42 iones en total -Ca, Cu, Mg, Mn, Zn- y los 42 sobreviven a la preparacion. Igual que en REC-08 con las cadenas, el riesgo de defecto de produccion no se materializa y no hay nada que reparar por esta via. (2) AGUAS, Y AQUI ESTA EL HALLAZGO: 1,788 aguas cristalograficas en los sitios de union, CONSERVADAS AL 100%. No es que no se pierdan: es que el pipeline las MANTIENE TODAS. Verificado directamente sobre rec.pdbqt, que es el receptor que Vina usa: 10gs lleva 169 atomos de HOH de 4,137 totales, 1a30 lleva 216 de 2,049 -HOH es su segundo residuo mas comun- y 1bcd 213 de 2,710. Vina las ve como parte del receptor: ocupan volumen y entran en la rejilla de afinidad. LA POLITICA DE FACTO QUEDA IDENTIFICADA. FEP-02 conto 'mediana de 10 aguas en el sitio, ninguna documentada como estructural o desplazable' y lo dejo como documentacion pendiente. Ahora se sabe cual es la politica que nadie declaro: CONSERVARLAS TODAS. Es una decision de modelado legitima y frecuente -tambien lo es lo contrario- pero es una decision, tiene consecuencias sobre el docking, y no esta escrita en ningun sitio. ANTECEDENTE QUE LO CONECTA: el incidente de REC-07 registro que pasar el PDB crudo con sus 387 aguas devolvio scores positivos de +23 a +33; alli se corrigio la preparacion PARA ESE EXPERIMENTO, y el material de produccion de molflex sigue conservandolas. HIPOTESIS, NO CLAIM: una pose que exija desplazar una agua conservada no puede encontrarse, de modo que las aguas retenidas son un candidato para parte del deficit de cobertura. NO se afirma aqui y hay evidencia en contra: MF-33 alcanzo 26 de 33 con ESTE MISMO receptor dockeando flexible, asi que las aguas no son el bloqueo principal del estrato dificil. Queda como hipotesis contrastable para los 7 que siguen sin cubrirse. LIMITACIONES DECLARADAS ANTES: emparejamiento POR COORDENADA con 0.5 A de tolerancia y no por identidad de residuo, porque la preparacion renumera; un atomo desplazado mas de 0.5 A contaria como perdido, de modo que el recuento de perdidas es COTA SUPERIOR -y salio cero, lo que refuerza el negativo-. Cobertura 116 de 203: los 87 restantes son todos de valtest y carecen de rec.pdbqt, la misma asimetria de material que registro REC-08.
- Hashes de dataset: 1 archivo(s) con SHA-256
- Hashes de assets: 1 archivo(s) con SHA-256

## Flujo de trabajo

1. `init`: crea este directorio con `manifest.json` prellenado y skeletons vacíos.
2. Ejecutar el experimento: escribir `metrics.json`, `per_complex.jsonl` y `failures.jsonl`.
3. `validate`: verifica `manifest.json` contra `manifest.schema.json`.
4. `seal`: registra los SHA-256 de datasets/modelos/binarios/assets y congela el manifest.
5. `finish`: escribe la decisión (GO/NO_GO/INCONCLUSIVE), la razón y la duración.
6. `maintain`: documenta de forma auditada los assets sellados que cambian tras el sello.

Después del `seal`, `validate` falla si cualquier archivo sellado cambia o desaparece.

## Inmutabilidad post-seal

- No se permite volver a sellar un experimento ya sellado (protege el cegamiento FND-05).
- `finish` y `maintain` son las únicas operaciones que modifican `manifest.json` después del sellado.
- `maintain` solo actualiza `assets_hashes` y registra cada cambio en `seal_maintenance`; datasets/modelos/binarios son inmutables.
- El README.md regenerado por `seal`/`finish`/`maintain` es la excepción documentada a la regla anterior.
- Los artefactos de producción permanecen fuera de este árbol (docs/49, sección 17).

## Archivos

- `manifest.json`: registro único del experimento (config, hashes, código, ambiente, salida).
- `metrics.json`: métricas agregadas del experimento.
- `per_complex.jsonl`: una línea JSON por complejo evaluado.
- `failures.jsonl`: una línea JSON por fallo.
- `README.md`: este archivo.
