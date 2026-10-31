# Modo sombra MolChat (§16.3) — registro de comparación

> **Registro histórico:** esta nota describe la rama en `36a186ef`. El selector beta y el panel clásico se retiraron en commits posteriores de la rama; las instrucciones para alternar entre ellos ya no describen la versión actual. Sus resultados no sustituyen las pruebas del código posterior ni del instalador.

El panel nuevo vive tras el flag `molchat-beta` (localStorage, `MolChatBetaSwitch`;
clásico por defecto) desde `a4b81363`. Esta nota registra la comparación que
pide §16.3 y lo que queda en manos del propietario. Rama `feat/molchat-plataforma-cr`
en `36a186ef`; sidecar `moldesign-molchat@35be9a7` (vendorizado `22d06f33`).

## Comparación ejecutada (2026-10-28, esta máquina)

| Frente (§16.3) | Cómo se midió | Resultado |
|---|---|---|
| Respuestas deterministas idénticas o mejores | Suite portada de 43 casos (`tests/quality/`, mismas queries y validadores adaptados del interno): `pytest tests/quality/` | **43/43** + test de latencia en verde (44 passed, 1 skipped: pata de proveedor sin fijar) |
| Cero fugas adversariales | Gate interno `test_gate_molchat_adversarial.py` en la rama + gate portado `tests/adversarial/` en el repo del sidecar | **18/18** interno, **16/16** portado (2 N/A por diseño desde Fase 2) |
| Latencias deterministas no peores (listón interno: 60–270 ms) | `test_deterministic_turns_answer_within_300ms` + sonda p95 (1000 turnos intent, 1200 respondedores) | Turnos <300 ms por test; **p95 intent 0,04 ms, respondedores ≤0,02 ms** (tres órdenes bajo el listón; la diferencia no es artefacto de máquina) |
| Convivencia sin regresión | Suite backend afectada (host, frontera, SBOM, auth, CR) + mount UI | **74 passed** backend, **7/7** mount, tsc limpio |

## Lo que NO se pudo correr aquí (bloqueo honesto, no verde fingido)

- **Suite interna con LLM** (`backend/quality_suite.py`): exige `qwen2.5-1.5b-instruct-q4_k_m.gguf`
  y no hay pesos en esta máquina (`tools/llama/` trae el binario, ningún `.gguf`).
  Falla antes del primer caso (`get_local_llm()` → None). No bloquea la sombra:
  el criterio §16.3 es la capa determinista (medida arriba) y la barra portada
  43/43 corre sin pesos.
- **Patas con proveedor del sidecar** (local y nube, criterio §16.4 para el corte):
  pendientes de modelo local o claves + consentimiento. Mismo bloqueo (pesos/claves),
  registrado para 6.6.

## Procedimiento pendiente del propietario (sesiones reales, §16.3)

1. Arrancar el escritorio de esta rama, abrir el panel, activar `MolChat nuevo (beta)`
   (esquina inferior izquierda; persiste en localStorage).
2. Repetir 3–5 sesiones reales recientes (propiedades, comparación, ranking,
   historial, un inválido): anotar divergencias del nuevo frente al clásico.
3. Criterio: ninguna respuesta factual peor; cualquier número sin evidencia es
   defecto bloqueante del corte (abrir issue con query + captura de ambos paneles).
4. Apagar la beta y confirmar que el clásico sigue intacto (default sin cambios).

Con sesiones reales sin divergencias + patas con proveedor en verde, §16.4
autoriza el corte (6.6).
