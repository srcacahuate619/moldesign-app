# FEP-03

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El material contiene series congenericas suficientes para que la ruta FEP+ sea aplicable

## Protocolo

Referencia: `auditoria sin docking: agrupacion de los 203 por identidad de secuencia (k-meros, umbral 0.90) y MCS por pareja dentro de cada diana; umbrales declarados antes (cobertura MCS >=0.70, perturbacion <=10 atomos)`

## Gate

auditoria sin gates; se cuenta cuantas parejas serian utilizables por FEP+

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6bae87c3cda6de687a37b19f2b7dd219cd53e053`, dirty=True

## Estado

- Creado: 2026-08-19T03:53:19.319690+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-19T03:53:20.099022+00:00)
- Finalizado: 2026-08-19T03:53:20.278024+00:00
- Razón de la decisión: La ruta FEP+ es aplicable pero solo en una fraccion: 91 parejas utilizables sobre 18 dianas, de 487 evaluadas (19%). Varias son de libro -1fkg/1fkh, 1dhi/1dhj, 1if7/1if8 con MCS de 26-33 atomos y perturbacion 0-. Pero el material NO esta construido para eso: 104 dianas distintas para 203 complejos, o sea la mitad de los complejos son la unica entrada de su diana; y la mediana global es cobertura MCS 0.50 con perturbacion de 27 atomos. Implicacion de diseno: el conjunto se armo para entrenar un selector de poses -maximizar diversidad de dianas- y eso es lo contrario de lo que necesita FEP+, que quiere pocas dianas con muchos analogos. Demostrar la ruta completa exigiria cohortes construidas al reves; PDBBind las tiene (el grupo mayor aqui es de 23 miembros). Se corrigio un bug propio: la primera pasada dio cobertura 1.11 y perturbacion -2, ambas imposibles, porque FindMCS contaba el hidrogeno retenido que GetNumHeavyAtoms no; con RemoveAllHs las parejas aptas bajaron de 96 a 91. Limitacion: la agrupacion por k-meros no distingue mutantes puntuales (que para FEP+ SI serian dianas distintas) y puede unir isoformas; ambos sesgos inflan el conteo, asi que 91 es una COTA SUPERIOR.
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
