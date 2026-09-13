> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# Stress Test Breakpoint -- 2026-07-06T19:09:34.945793

| Metric | Value |
|---|---|
| Modelo | Qwen2.5-1.5B Q4_K_M |
| n_ctx | 16384 |
| Modo | speed |
| Mensajes totales | 1000 |
| Exitosos | 1000 |
| Fallidos | 0 |
| Tiempo total | 12443.0s |
| Input tokens | ~25241 |
| Output tokens | ~210615 |
| Max contexto | 1438.8% |
| Hallucinations | 1 |

## Break Point
No se rompio

## Degradacion de Calidad
Detectada en msg #1, ~0t, recall: 0.12
