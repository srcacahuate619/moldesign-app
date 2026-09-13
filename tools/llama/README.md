# Directorio del binario `llama-server.exe`

Este directorio aloja el servidor LLM subprocess usado por MolChat (ver `docs/33_MIGRATION_LLAMA_SERVER.md`).

## Contenido esperado

```
tools/llama/
├── llama-server.exe       # binario oficial de ggerganov/llama.cpp (release stable)
├── *.dll                  # dependencias runtime del binario (si las pide)
└── SHA256SUM.txt          # hash del binario, para trazabilidad
```

## Cómo obtener el binario

1. Ir a https://github.com/ggerganov/llama.cpp/releases
2. Seleccionar el tag más estable compatible con Qwen2.5-1.5B-Instruct GGUF (q4_k_m quantization, formato B1024+).
3. Descargar el asset `llama-*-bin-win-*.{zip|7z}`.
4. Extraer SOLO `llama-server.exe` y sus `.dll` dependientes a este directorio.
5. Calcular `sha256sum llama-server.exe > SHA256SUM.txt` (o `Get-FileHash` en PowerShell).

## Por qué no está commiteado

El binario y sus deps son ~10-20 MB. Se excluye de git vía `.gitignore`. El instalador Tauri los empaqueta desde aquí hacia el usuario final — **0 fricción: el usuario nunca ve este paso**.

## Verificación

El backend valida la existencia del binario en `is_local_llm_available()` (ver `services/ai/local_llm.py`). Si falta, MolChat se deshabilita con un mensaje claro — no crashea la app.

## Versión pinned

_Release tag:_ `b10199` (latest stable, 2026-07-30)
_Commit:_ `b4ca032ae3729516943884786de4ae39fba0bbca`
_SHA-256 del ZIP fuente:_ `b10b8cbcc0fef99771daf13cfea426d1dde4baf36618a9b4c4c30a6f79115650`
_SHA-256 de `llama-server.exe`:_ `338827a298c806afb8ef678d7903ee7fe2078faed40797295c36a52aace73bfb`
_Backend:_ CPU (x64) — máxima compatibilidad, 20 archivos, ~37 MB descomprimido.

> **Nota:** Si en el futuro querés habilitar aceleración CUDA, descargá
> `llama-b10199-bin-win-cuda-12.4-x64.zip` (239 MB) y los CUDA runtime DLLs
> (`cudart-llama-bin-win-cuda-12.4-x64.zip`, 373 MB). Reemplazá los binarios
> CPU por los CUDA. El wrapper `local_llm.py` auto-detecta la GPU
> y ajusta `-ngl` en consecuencia — no requiere cambios de código.
