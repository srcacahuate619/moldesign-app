# ABS-TR-01-VALIDEZ-R1 — desviaciones (append-only)

## 2026-10-24 — firma antes de evaluar

- `REGISTRO_PREVIO.md` SHA-256 `330d1b119a01b787295713718095c3bc1ec1eb5acdcb4f686abc398843a67520` (copia idéntica en `entrada/REGISTRO_PREVIO_R1.md`). Desde aquí no se edita.
- Entrada copiada byte a byte de `ABS-TR-01-VALIDEZ/entrada`.

## 2026-10-24 — ejecución

- 29 sistemas en dos shards en paralelo (cápsulas 1 y 2), un intento cada uno salvo 8WTW, que falla en la preparación (Meeko) en sus dos intentos, como en ABS-TR-01-VALIDEZ; 1DIY se detiene en el preflight, también como antes. Sin deriva.
- `analizar` escribió las métricas y falló al imprimir una flecha en la consola cp1252; repetido con `PYTHONIOENCODING=utf-8`, mismo resultado.
