# Auditoría final del MVP — resultados, producto y valor

**Fecha:** 2026-08-24  
**Veredicto:** **GO condicional a piloto privado. NO-GO a lanzamiento comercial general.**  
**Condición técnica pendiente:** integrar la evidencia estructural al flujo
productivo y, sólo después, completar instalador y smoke test de Gate 4.

## 1. Qué producto existe ahora

MolDesign convierte una estructura proteica y una molécula o serie de ligandos
en un estudio computacional inicial ejecutado localmente, con entradas,
configuración, cobertura, excepciones, procedencia y artefactos verificables.

No es un sistema que descubre fármacos ni responde si una molécula será eficaz.
Su unidad de valor es una **hipótesis estructural auditable y transferible**.

Dos flujos forman el MVP:

1. **Caso individual:** preparar una hipótesis, ejecutar una evaluación y emitir
   un dossier del caso con lo producido, lo no evaluado y los próximos pasos.
2. **Cohorte comparable:** congelar un receptor, configuración y serie de
   ligandos; ejecutar las moléculas comparables; declarar cobertura,
   excepciones y evidencia; exportar PDF y ZIP verificable.

## 2. Qué significan los resultados

| Resultado | Sí permite afirmar | No permite afirmar |
|---|---|---|
| Preflight `ready` | Las entradas se pudieron leer y comparten una configuración ejecutable | Que la molécula sea activa o adecuada |
| Afinidad Vina observada | Cómo ordenó Vina estas moléculas bajo este protocolo | Energía libre experimental, probabilidad de unión o eficacia |
| `completed` | El motor produjo el resultado previsto | Que la hipótesis sea físicamente correcta |
| `failed` / `not_evaluated` | Qué ocurrió en la tubería y cuál fue la cobertura | Evidencia negativa sobre la molécula |
| EF / ROC-AUC | Asociación retrospectiva con etiquetas explícitas dentro de esa cohorte | Validación prospectiva o capacidad general de descubrir fármacos |
| Fingerprints y checksums | Identidad e integridad de entradas, ejecución y paquete | Validez científica por sí solos |

Las métricas 0–100 dejaron de gobernar el producto. La afinidad se presenta con
su unidad y nombre, los denominadores son explícitos y las métricas se abstienen
cuando no son evaluables.

## 3. Valor para el cliente

El cliente inicial más claro es un laboratorio académico, grupo de química
computacional o biotech pequeña que ya dispone de una estructura y una serie
reducida de ligandos, pero carece de una tubería local consistente y de una
forma seria de entregar lo calculado.

MolDesign aporta valor al:

- prevenir ejecuciones sobre entradas inválidas o cohortes incomparables;
- evitar que moléculas descartadas desaparezcan del denominador;
- conservar exactamente receptor, configuración y ligandos utilizados;
- separar resultados, fallos y abstenciones;
- reducir trabajo manual de documentación y transferencia;
- producir un paquete que otra persona puede verificar;
- mantener estructuras y resultados en el equipo local.

El trabajo que se compra o adopta no es “encuéntrame un fármaco”, sino:

> “Ayúdame a ejecutar y documentar correctamente esta hipótesis computacional
> inicial para decidir qué revisar, repetir o enviar al siguiente método.”

## 4. Fortaleza actual

- Contratos de caso y cohorte explícitos.
- Cohortes con un receptor y configuración común.
- Entradas, inválidas y duplicados conservados.
- Ejecución durable, cancelable y reanudable.
- Receptor preparado almacenado y consumido de forma inmutable.
- XGBoost/ML fuera del camino de cohortes.
- Cobertura y denominadores visibles.
- Dossier y paquete con un protocolo común de checksums.
- Narrativa principal alineada en español e inglés.
- Aplicación local y abierta como diferenciador real.

## 5. Límites que impiden sobreprometer

### P0 — antes de distribuir el instalador

- La validación geométrica/física existente debe ejecutarse sobre la pose
  realmente seleccionada, persistirse y aparecer en UI, dossier y paquete.
- La selección de pose debe conservar Vina top-1, declarar modelo, confianza y
  abstención, y nunca sustituir una pose silenciosamente.
- La representación canónica y la procedencia de preparación deben acompañar
  el veredicto para no repetir el artefacto histórico de hidrógenos.
- Gate 4 debe terminar con instalador y smoke test en entorno limpio.
- La app no puede depender de un servidor de desarrollo ni mostrar conexión
  rechazada durante el arranque normal.

### P1 — primera actualización científica después del piloto

- `MIN_N_FOR_METRICS = 10` es una política operativa, no un análisis de
  potencia. EF/ROC-AUC deben seguir siendo secundarios.
- Falta medir estabilidad entre semillas/repeticiones dentro del producto.

### P1 — validación de mercado

La utilidad técnica está demostrada por contratos y pruebas; la disposición a
pagar no. Antes de desarrollar más ciencia se necesitan pilotos reales.

## 6. Criterio de piloto

Lanzar a 5–10 usuarios del perfil objetivo y medir:

- tiempo desde instalación hasta primer dossier válido;
- porcentaje de cohortes que superan preflight;
- cobertura de ejecución y causas de abstención;
- tiempo ahorrado al preparar y documentar una corrida;
- si el ZIP permite a otra persona entender y verificar el estudio;
- número de errores/incomparabilidades detectados antes de gastar cómputo;
- repetición de uso en una segunda hipótesis;
- solicitud espontánea de soporte, colaboración o funciones de equipo.

## 7. Decisión de producto

Mantener ML, GNN y nuevos experimentos fuera del camino crítico del MVP.
Pueden regresar como señales opcionales sólo cuando tengan contrato,
aplicabilidad, incertidumbre y abstención demostrados.

La prioridad antes del instalador es:

1. integrar selección y validación geométrica/física como evidencia trazable;
2. auditar el recorrido completo y sus degradaciones honestas;
3. compilar instalador y ejecutar smoke test limpio;
4. iniciar pilotos observados y corregir fricción;
5. sólo después ampliar modelos o automatización.

## 8. Posicionamiento aprobado

> **MolDesign es una herramienta local y abierta para preparar hipótesis
> estructurales, ejecutar evaluaciones iniciales comparables y entregar la
> evidencia computacional con sus supuestos, cobertura, excepciones y
> procedencia.**

No utilizar como promesa principal “drug discovery”, “diseño de medicamentos”,
“mejor candidato”, “probabilidad de éxito” ni “pose físicamente validada”.

## 9. Modelo de adopción y sostenibilidad

MolDesign seguirá un modelo **open-source first**: el núcleo local debe ser útil
por sí mismo y permitir, sin pago, ejecutar la evaluación, inspeccionar los
controles científicos, exportar la evidencia y verificar su reproducibilidad.

Una futura suscripción **MolDesign GO** será opcional y no bloqueante. Podrá
vender conveniencia —sincronización y respaldo, colaboración de equipos,
cómputo gestionado, actualizaciones administradas, soporte prioritario y
funciones organizacionales—, pero no ocultará detrás de pago:

- controles de validez o advertencias científicas;
- procedencia, incertidumbre o abstenciones;
- formatos abiertos, exportación o verificación local;
- reproducibilidad básica ni acceso a los resultados propios.

La capa comercial financiará una mejor experiencia operativa; no comprará un
veredicto más favorable ni una ciencia “más verdadera”.
