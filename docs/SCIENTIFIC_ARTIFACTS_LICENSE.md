# Política interna — artefactos científicos sellados

Estado: 2026-09-06. Este documento no cambia los bytes de
scripts/artifacts_science/, que son evidencia experimental sellada.

Los 20 modelos por fold que viven bajo RS-01B/fold_models y RS-04-OOF/fold_models
son artefactos de evidencia, no pesos del producto distribuido. Se conservan
para que los resultados publicados de esos experimentos puedan auditarse y
reproducirse. El contenido de esos directorios está cubierto por los avisos y
las condiciones que correspondan a la corrida que los produjo; no se debe
inferir que la licencia PolyForm del código los relicencia.

La guarda scripts/check_model_license_boundary.py los enumera en cada ejecución
y los excluye de la generación de marcadores locales por dos razones:

1. AGENTS.md prohíbe editar el árbol sellado.
2. Añadir un marcador junto a la evidencia podría alterar la interpretación de
   sus hashes o convertir una decisión científica en una suposición legal.

Antes de redistribuir estos modelos fuera del repositorio hay que confirmar
autoría, licencia y permisos de cada experimento. Hasta entonces:

- no se copian al runtime de producción;
- no se adjuntan a un release ni a un repositorio de modelos;
- no se anuncian como pesos de producto;
- cualquier cambio de licencia se registra como decisión del titular y se
  acompaña de un re-sellado científico, nunca de una edición silenciosa.

El estado que imprime la guarda (“sin marcador en sitio”) es deliberado:
significa “evidencia sellada pendiente de decisión jurídica”, no “olvido” ni
“aprobación automática”.
