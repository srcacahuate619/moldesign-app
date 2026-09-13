# MF-33-B-RET-R1 — preregistro de repetición completa

## Motivo y alcance

`MF-33-B-RET` quedó interrumpido en 43/48 complejos y no retuvo la geometría ni
los pares por pose. Su copia forense sellada `MF-33-B-RET-PARTIAL` es
`INCONCLUSIVE` y no se usa para elegir parámetros. Este R1 reejecuta **los 48**
complejos de `MF-33` bajo el contrato ya publicado en `MF-33-B-RET-PRE`; la
única ampliación es trazabilidad técnica, no una modificación de hipótesis,
cohorte, configuración, umbral ni lectura.

## Protocolo congelado

- Ligandos: todos los `conf*.flex.pdbqt` de los 48 PIDs de `MF-33`.
- Vina: exhaustiveness 8, num_modes 9, seed 42, caja cúbica 25 Å, `--cpu 1`.
- SINGLE: todas las poses de `conf0`, ordenadas por score Vina.
- ENSEMBLE: todas las poses de todos los conformeros, ordenadas por score Vina.
- Métrica: `rmsd_pose_pocket`, sin alineamiento; hit si `<=2.0 Å`.
- Sin rescoring, sin deduplicación, sin cambio de producción.

## Retención y reanudación

Cada dock conserva el PDBQT original en `raw_pdbqt/` y stdout/stderr en `logs/`.
Cada complejo terminado publica atómicamente un checkpoint y sus registros de
pose con identidad `pid|confN|modelM`, score, RMSD, hash y rutas de evidencia.
Al reiniciar, solo se omiten complejos cuyo checkpoint completo ya existe. No
existe opción de borrar/reinicializar output. Un fallo de Vina, parseo o mapeo
es ITT: se registra en `failures.jsonl` y hace fallar G0.

## Gates y lectura (idénticos al contrato padre)

G0 técnico exige 48/48 complejos completos y cero fallos. G1 exige que el
oráculo ENSEMBLE reproduzca `rmsd_min` del brazo B sellado de MF-33 dentro de
0.001 Å en al menos 95% de los complejos. Si G0 o G1 falla, la lectura primaria
es `NO_LEER_GATES_TECNICOS`.

Con G0/G1 aprobados, McNemar exacto bilateral se calcula para top-1, top-5 y
oráculo. La decisión exacta es:

1. `LA_VENTAJA_LLEGA_AL_USUARIO` si oráculo y top-1 mejoran (`p<0.05`);
2. `EL_CUELLO_SE_DESPLAZA_A_LA_SELECCION` si mejora oráculo pero no top-1;
3. `SIN_EFECTO_EN_LA_ENTREGA` en los demás casos.

Se reporta también el margen de selección y PoseBusters sobre el top-1 de cada
brazo. PoseBusters es descriptivo: no modifica ningún gate.

## Límites

Es una cohorte de desarrollo ya observada parcialmente y una comparación de
redocking con pocket conocida; no es validación externa ni end-to-end. La
retención permite auditoría posterior, no convierte el resultado en evidencia
ciega o confirmatoria.
