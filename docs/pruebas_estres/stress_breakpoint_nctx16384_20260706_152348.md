> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# Stress Test Breakpoint -- 2026-07-06T15:23:48.241400

| Metric | Value |
|---|---|
| Modelo | Qwen2.5-1.5B Q4_K_M |
| n_ctx | 16384 |
| Modo | speed |
| Mensajes totales | 200 |
| Exitosos | 200 |
| Fallidos | 0 |
| Tiempo total | 3020.5s |
| Input tokens | ~5113 |
| Output tokens | ~39596 |
| Max contexto | 272.0% |
| Hallucinations | 1 |

## Break Point
No se rompio

## Degradacion de Calidad
Detectada en msg #1, ~0t, recall: 0.12
