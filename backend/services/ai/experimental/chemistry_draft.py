"""
ChemistryDraftModel — speculative decoding draft que nunca devuelve array vacío.

El problema del LlamaPromptLookupDecoding original:
  Cuando no encuentra n-gram matching, devuelve np.array([], dtype=intc)
  Ese array vacío causa broadcast error en CUDA (batch size 0).

Este draft:
  - Intenta n-gram lookup (max_ngram_size, num_pred_tokens configurables)
  - Si NO encuentra match, devuelve input_ids[-1:] (último token repetido)
  - NUNCA devuelve vacío → no hay crash en CUDA

---

⚠️  EXPERIMENTAL — DEUDA DOCUMENTADA, NO CÓDIGO ZOMBIE

Este módulo vive en `services/ai/experimental/` porque:

1. Fue implementado para acelerar la generación de MolChat con el modelo local
   Qwen2.5-1.5B-Instruct (Q4_K_M) usando speculative decoding (MTP).

2. Se descartó en producción: la familia Qwen 2.x no soporta de forma estable
   la API `draft_model=` de `llama-cpp-python` para este caso de uso.

3. Se preserva como PLANTILLA para futuros experimentos con modelos locales
   que sí soporten MTP nativo (Phi-3 mini, Llama 3.2, Gemma 2, etc.).

El path `experimental/` más este README explícito evita que sea malinterpretado
como feature viva del codebase. Es deuda documentada, no implícita.

---

2015 — ver `docs/33_MIGRATION_LLAMA_SERVER.md §4.D5` para el contexto completo
de por qué este archivo sobrevive al cleanup del módulo `local_llm.py` al migrar
de `llama-cpp-python` (in-process) a `llama-server.exe` (subprocess HTTP).
"""

import numpy as np
from llama_cpp.llama_speculative import LlamaDraftModel


class ChemistryDraftModel(LlamaDraftModel):
    def __init__(self, ngram_size: int = 2, pred_tokens: int = 3):
        self.ngram_size = ngram_size
        self.pred_tokens = pred_tokens

    def __call__(self, input_ids: np.ndarray, /, **kwargs) -> np.ndarray:
        n = min(self.ngram_size, input_ids.shape[0] - 1)
        if n < 1:
            return input_ids[-1:]

        # sliding window: buscar dónde aparecen los últimos N tokens antes
        windows = np.lib.stride_tricks.sliding_window_view(input_ids, (n,))
        last_ngram = input_ids[-n:]
        matches = np.all(windows == last_ngram, axis=1)

        # Excluir la última ventana (es el propio n-gram)
        match_indices = np.nonzero(matches[:-1])[0] if len(matches) > 1 else []

        for idx in match_indices:
            start = idx + n
            end = min(start + self.pred_tokens, input_ids.shape[0])
            if start < end:
                return input_ids[start:end]

        # Fallback seguro: repetir el último token (nunca array vacío)
        return input_ids[-1:]
