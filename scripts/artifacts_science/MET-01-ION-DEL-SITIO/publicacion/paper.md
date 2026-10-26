---
titulo: "MET-01 no puede comparar el ion: la evaluación pierde la whitelist"
entradilla: "INCONCLUSIVE. La variante CON conserva Zn, pero las seis tentativas CON del piloto 1BN1 usaron el receptor SIN. No se inició la fase confirmatoria ni se estimó el efecto del ion."
---

**INCONCLUSIVE.** MET-01 se detuvo en el piloto porque el producto cambió el
receptor del brazo CON. La evidencia no responde si conservar el ion mejora
el redocking. Se mantiene la abstención; cualquier arreglo del producto y
repetición requieren otro encargo y un experimento MET-01-R1.

## Qué se fijó antes de acoplar

Producto `f0e6408668fa8ecbecb417cf39621928fdfee886`, Vina 1.2.7, Meeko 0.7.1, Python embebido 3.11.9,
RDKit 2025.9.6 y PoseBusters 0.6.5 `dock`, con H reconstruidos bajo
MF-33-H-COR. Exhaustividad 8, nueve poses solicitadas, un conformador,
CPU=4 y semillas 42–46. Prerregistro: `32e552ebe823d8e289582102d52424bce3cd6d4a`.

La población fija tiene 41 entradas y 52 iones: 35 entradas coordinan un ion
por geometría del cristal y seis son controles. Los SMILES del CCD, sus URL,
fechas y hashes, microestados normales y formas diagnósticas se congelaron
antes de Vina. Se conservaron las definiciones completas.
[Diccionario wwPDB](https://www.wwpdb.org/data/ccd).

Se reutilizan sin modificar `Backend.evaluar`, `_cristal`, `_neutro_sin_h`
y `_top1` de CAL-8HFI-01. RMSD simétrico de átomos pesados, sin alinear,
del top-1 comprobado contra el PDBQT; todos los RMSD de las poses devueltas
se conservan. Reproduce una entrada si ≥3 de 5 semillas dan RMSD ≤2 Å
y **todas** las semillas cuyo RMSD cumple son físicamente válidas.

## Potencia y reconocimiento

Prueba pareada exacta de signos, bilateral, α=0,05. Seis discordancias 6:0
dan p=0,03125: 17,14 puntos sobre n=35, un límite de significación, no de
potencia. El efecto mínimo preregistrado fue 40 puntos de tasa pareada,
bajo el supuesto explícito de 50 % de discordancias: potencia de 94,76 %
con n=35, 82,02 % con n=25 y 87.24 % con las 28 entradas
principales previstas. A 80 % de potencia son detectables 33,7 puntos con
35 y 39,4 con 25 bajo ese mismo modelo. La tabla de sensibilidad está sellada.
No se garantiza esa potencia para tasas desconocidas de discordancia.

Dos preparaciones en procesos distintos dieron hashes repetibles en 39 SIN
y 37 CON. SIN coincide con el catálogo en 38 de las 39 preparables. Se
excluyeron antes de docking nueve entradas: 1VKG, 5E92, 5I3T, 6S1Y, 6S1Z, 6USR, 8UBR, 8WGR, 9GKV.
Son siete principales y dos controles. 8UBR conserva dos ATP adicionales
en la variante, al perderse `site_ligand` durante la ingesta; se excluyó
antes de Vina, sin arreglarlo. Las demás causas de preparación o referencia
no casable se documentan por entrada. Quedaban 28 principales y cuatro controles.

Se fijó antes de medir un cambio del gate propuesto: no pérdida de
reproducción en todos los controles evaluables, con mínimo cuatro de seis.
Dos controles ya eran inevaluables por preparación/referencia. Un n<25 o
más de 30 % de exclusiones principales exige INCONCLUSIVE. El cambio no
permite afirmar ausencia de daño en los controles omitidos.

## Qué reveló el piloto

La API creó CON de 1BN1 con `cofactors_whitelist=["ZN"]` y hash
`e23dabe7f14c443a8df26a8ec8aa0ff5d2d3efd90370e4c5d4ee65dd6ff5c08b`. Preflight y pipeline usan
`_coerce_hotspots`, cuya implementación conserva sólo elementos `dict`:
la lista de cadenas se convierte en `[]`. La evaluación vuelve a preparar
el receptor sin Zn. Su hash es `96e0aa3134454f59a8f8bc3ef365ae8412c3c5bd3e67490988e7e204acb6fed8`, el de SIN.
La copia del receptor **utilizado**, los logs de Vina, los resultados
persistidos y los seis crudos CON confirman el mismo cambio.
Las funciones originales prueban también el descarte de `MG`, `CA` y `K`;
esto demuestra el mecanismo, no resultados de redocking en esas entradas.

| Evidencia del piloto | Cantidad |
|---|---:|
| SIN con resultado completo y receptor esperado | 5 semillas |
| Intentos solicitados CON que utilizaron SIN | 6, dos por semilla 42–44 |
| Terminales rechazados por el guardián de receptor | 3 de 8 (37,5 %) |
| Pares válidos en el piloto | 0 |
| Corridas confirmatorias | 0 de 380 previstas |
| Pares principales / controles al cierre | 0 / 0 |

El limitador detuvo y cerró la cápsula al superar 30 %. El error es una
invalidación del brazo por el producto; no prueba que Vina fallara ni que el
ion empeorara. Los terminales originales conservan la etiqueta genérica
`INFRASTRUCTURE_FAILURE` del guardián, junto con la causa exacta. No se
reclasifican como poses fallidas para inflar el resultado científico.
Antes hubo dos fallos de Vina por MAX_PATH y dos detenciones de montaje
sin evaluación: se conservan aparte y las correcciones del arnés están en
la bitácora. No se sobrescribió ningún crudo ni terminal.

Los cinco SIN del piloto dieron 0/5 RMSD ≤2 Å, 5/5 top-1 válidos
y 0/5 ambos. Son datos del piloto, fuera del gate. Los seis intentos
CON no son seis semillas independientes ni un brazo con metal.
La prueba de signos no es aplicable con cero pares; el p=1 del JSON es la
convención del algoritmo para cero discordancias, no una inferencia.
El piloto pareado quedó incompleto y no permite estimar el tiempo total.

## El límite de PoseBusters y del diagnóstico

El reconocimiento usó coordenadas del cristal, nunca poses acopladas.
Meeko escribe los iones como `ATOM`; PoseBusters los excluye de la máscara
inorgánica por considerarlos proteína y de la máscara de proteína por su
elemento. Los 52 átomos metálicos cargados quedaron fuera de ambas máscaras:
46 pertenecían a la población y seis eran iones adicionales conservados por
código de residuo. Un PASA no valida su coordinación.
[API de PoseBusters](https://posebusters.readthedocs.io/en/latest/api.html).

Las seis formas diagnósticas representables para Zn se fijaron con reglas
químicas independientes y se contrastaron en dos procesos. No se ejecutaron.
El pH usado para expresarlas no estima su población de unión. Tampoco se
pudo medir la frecuencia de His con H en el nitrógeno coordinante durante
corridas CON reales, porque ningún receptor CON se acopló.

## Qué no dice y qué queda

No hay un NO_GO científico contra conservar el ion, una demostración de
equivalencia ni una recomendación de whitelist por receptor. El redocking
previsto usa el propio cristal: aun completo no demostraría cross-docking,
afinidad, actividad, energía de coordinación, calibración ni readiness FEP.
Las entradas comparten familias proteicas; no equivalen a 35 dianas
independientes. Vina tampoco añade por conservar un ion los parámetros y
pseudoátomos del protocolo AutoDock4Zn.
[Documentación de AutoDock](https://autodock-vina.readthedocs.io/en/latest/docking_zinc.html).

Se conservan el prerregistro y toda la evidencia producida. El catálogo,
M5 y el producto siguen en f0e64086. La confirmación no se lanzó, por lo que
no hubo intervalo confirmatorio con ediciones. Los sellos usan rutas del
repositorio y los archivos científicos están versionados. La única
desviación de alcance fue un temporal propio creado fuera de scripts/docs
durante la primera inspección de PoseBusters, retirado después; consta en
la bitácora. El runtime no viaja por git y sus hashes sí.
