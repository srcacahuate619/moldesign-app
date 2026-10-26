# Decisiones pendientes para revisión del propietario/Claude

Las recomendaciones siguientes no son decisiones tomadas por el propietario.

| ID | Decisión | Opciones y consecuencias | Recomendación |
|---|---|---|---|
| D1 | Política iónica Na/Cl/K y representación para Vina | A) retirar todo; sencillo pero representa NET sin su estado iónico. B) conservar iones con parámetros/validación explícitos; puede requerir trabajo y bloquear. C) probar ambos; si sólo pasa el modelo sin iones, el resultado es exploratorio. | No ejecutar calibración hasta validar B o aceptar C como exploratorio. En 8HFI se deposita Cl en la caja y 8WGR ubica K en Na1. |
| D2 | Estructura primaria | 8HFI tiene DSM en S1 y 2.50 Å global; 8WGR tiene DSM, Cl y K en Na1 a 4.346 Å, pero la receta actual bloquea al quitar K. | 8HFI primaria y 8WGR como sensibilidad después de resolver iones; preferencia provisional porque las condiciones del ensayo 2006 faltan. |
| D3 | Uso de 8WTX | Bupropión estabiliza estado inward-facing y su artículo describe inhibición no competitiva en un bolsillo distinto al de ziprasidona. No equivale al ensayo de desplazamiento competitivo del panel. | No usar como estructura principal del panel CHEMBL853189. |
| D4 | Condiciones del assay y constructo | Recuperar de fuente primaria pH, buffer, temperatura, radioligando/concentración, Kd, tiempo, método Ki, fuente y constructo. Sin ellos no se conoce el estado iónico experimental. | Mantener NO_ENCONTRADO hasta encontrar evidencia primaria; no importar protocolo ajeno. |
| D5 | Microestado a pH 7.4 y al pH del assay | Padres neutros, mono-protonados o di-protonados; los SMILES tienen dos aminas básicas y cada carga cambia el score. | Adjudicar pKa/especie para cada padre; si coexisten especies, congelar conjunto y regla de puntuación antes de docking. |
| D6 | Exclusiones químicas | Excluir estereoquímica parental sin resolver cuando el dato representa mezcla/enantiómero incierto; censurados requieren un modelo preregistrado. | Regla aplicada hoy excluye 0; mantiene 57 padres. No cambiar panel después de mirar scores. |
| D7 | Número de poses y exhaustividad | Protocolo candidato: 9 modos/exhaustividad 32; default de configuración: 5 modos/8 para docking general. La opción omitida por servicio puede usar default. | Propuesta: 32/9 explícitos según el candidato previo, con aprobación antes de freeze. |
| D8 | Seeds de redocking | Producto usa 42 por default; verificación requiere cinco seeds. | Propuesta reproducible 42,43,44,45,46; mismo receptor/ligando y registrar cinco RMSD. |
| D9 | Signo de Spearman | E_Vina más negativa es mejor; rho(E,pKi) esperada negativa, pero el criterio aprobado exige límite inferior positivo. | Definir Q=−E y evaluar rho(Q,pKi)>0; publicar también rho(E,pKi). Confirmar interpretación antes de correr. |
| D10 | Fallo de docking | Eliminar fallos altera n y sesga; imputar score inventa evidencia. | Una repetición técnica idéntica; si vuelve a fallar, gate calibrado falla y se publican fallo y análisis exploratorio complete-case. |
| D11 | Bootstrap/potencia | Cuatro clusters Murcko; 53/57 padres en uno. Bootstrap de cuatro unidades es frágil. | Mantener bootstrap preregistrado de clusters, 10,000 draw/seed42 y declarar fragilidad. Fisher 0.261 es sólo aproximación orientativa. |
| D12 | Resolución local S1 y constructo | Resolución local numérica S1, tags y constructo exacto no encontrados en los resúmenes RCSB/EMDB consultados. | Consultar mapas/metadatos detallados sólo si cambia elección; sin descargar mapas grandes para esta auditoría. |
| D13 | Hash final de entradas | SHA-256 del CSV actual: d5c7a4bb4b117acd6d670fba3a0815f2e6de9ca697c2d4cb3c91625d9a6a7751; es tabla de actividades y padres, no SMILES de especies ni receptor preparado. | Congelar nueva tabla con cada microestado, su carga y procedencia; fijar hashes CIF, receptor, receta, runtime y caja antes de ejecutar. |

## Gates abiertos

1. Justificar la política de iones y validar compatibilidad con Vina.
2. Adjudicar condiciones/constructo históricos o aceptar por escrito el gap.
3. Resolver los estados de 57 padres.
4. Confirmar 9 frente a 5 poses y la convención Q=−E.
5. Congelar panel químico final, receptor/receta/caja y hashes SHA-256.

