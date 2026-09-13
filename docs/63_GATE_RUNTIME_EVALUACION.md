# Gate runtime de Evaluación — protocolo de aceptación

**Estado:** APROBADO por recorrido runtime automatizado con binarios reales (2026-08-30).  
**Objetivo:** demostrar persistencia, reproducibilidad y aislamiento con una corrida real.

## Resultado ejecutado

- Script reproducible: `scripts/accept_evaluation_runtime.py`.
- Evidencia local: `tmp/evaluation-runtime-20260830T180225Z/`.
- Corrida: `22728caa-621d-4e90-a809-e7159fd88ad1`.
- Molécula: aspirina; receptor `7E2Y`, cadena `R`; AutoDock Vina `1.2.7`.
- Resultado persistido: `molecule_id=f3301985-e208-479e-b414-e2018f98fdd4`,
  afinidad agregada `-5.489096 kcal/mol`, receptor preparado
  `sha256:5f88e3ad04105755966e418839895ddc91b89a9c8a4d36f84df4f04efc362940`.
- Resultado vivo y reabierto después de reiniciar el backend: iguales en los campos
  científicos críticos del gate.
- Polling: no transportó SDF; `poses.sdf` se solicitó después del terminal.
- Dossier: ZIP generado con `task_id` exacto y poses registradas.
- Aislamiento: la cuenta B recibió `403/404` en status, resultado, poses, proteína,
  complejo y dossier (6/6 denegaciones).
- Regresión completa posterior: backend `933 passed, 3 skipped`.

Durante la ejecución se corrigieron tres defectos que impedían aprobar el gate: la firma
obsoleta de `7E2Y` en el catálogo nuevo (`A`/caja antigua en vez de `R`/caja curada), la
conversión de `pro_mmgbsa_steps: null` con `int()`, y el default `esmfold` que desviaba
small molecules a la ruta peptídica. También se separó el nombre del motor (`vina`) de su
versión (`1.2.7`) en el protocolo y se completaron sus fallbacks de procedencia.

## Preparación

- Usar una molécula pequeña, receptor oficial disponible offline y confórmero único.
- Registrar cuenta A, ID del caso, `task_id`, `molecule_id` y hora de inicio.
- No modificar receptor, cadena, caja ni protocolo entre la corrida y la reapertura.

## Recorrido obligatorio

1. Iniciar backend y aplicación desde cero; entrar con la cuenta A.
2. Crear el caso, ejecutar el preflight y guardar su fingerprint y advertencias.
3. Ejecutar una corrida real hasta `SUCCESS`; guardar el JSON de resultado y el dossier.
4. Confirmar en red que el polling de `status` no contiene SDF. Abrir después la vista de poses
   y comprobar que sólo entonces se solicita `/evaluation/files/poses/{molecule_id}`.
5. Cerrar completamente aplicación y backend. Iniciarlos otra vez sin borrar datos.
6. Entrar con la misma cuenta A, abrir el mismo caso y recuperar la corrida sin reejecutarla.
7. Comparar resultado vivo, resultado reabierto y dossier en los campos de la tabla siguiente.
8. Cerrar sesión, entrar con cuenta B e intentar acceder directamente a status, resultado,
   poses, proteína, complejo y dossier usando los IDs conocidos de A.

## Matriz de igualdad

Todos estos campos deben conservar valor y semántica; `null` debe seguir siendo `null`.

| Grupo | Campos mínimos |
|---|---|
| Identidad | `task_id`, `molecule_id`, SMILES canónico, receptor, cadena |
| Protocolo | motor y versión, seed, exhaustividad, poses, conformaciones |
| Estructura | centro/tamaño de caja, SHA-256 del receptor preparado |
| Resultado | afinidad, score total, pose seleccionada y unidades |
| Calidad | advertencias, componentes ausentes, cobertura y abstenciones |
| Artefactos | poses, proteína, complejo y manifiesto del dossier |

## Criterios de aprobación

- La cuenta A recupera exactamente la misma corrida después del reinicio.
- El dossier coincide con los campos científicos del resultado vivo y reabierto.
- El polling nunca transporta el SDF; la descarga es diferida hasta abrir poses.
- La cuenta B recibe `403` o `404` sin contenido ni metadatos de la corrida de A.
- No aparecen loaders permanentes, resultados vacíos, sustituciones ni reejecuciones silenciosas.

## Evidencia a conservar

- Capturas antes y después del reinicio.
- JSON vivo y reabierto, dossier descargado y log de solicitudes HTTP.
- Respuestas y códigos HTTP obtenidos con cuenta B.
- Versión de la app/backend y hashes de los artefactos comparados.

Si falla un punto, registrar un hallazgo estable `EVAL-RUNTIME-###`; no repetir la corrida hasta
guardar los artefactos y logs del fallo original.
