> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# Stress Test Breakpoint -- 2026-07-06T13:37:40.498346

| Metric | Value |
|---|---|
| Modelo | Qwen2.5-1.5B Q4_K_M |
| n_ctx | 16384 |
| Modo | speed |
| Mensajes totales | 80 |
| Exitosos | 80 |
| Fallidos | 0 |
| Tiempo total | 1342.9s |
| Input tokens | ~2076 |
| Output tokens | ~14492 |
| Max contexto | 107.8% |
| Hallucinations | 4 |

## Break Point
No se rompio

## Degradacion de Calidad
Detectada en msg #11, ~2001t, recall: 0.12
