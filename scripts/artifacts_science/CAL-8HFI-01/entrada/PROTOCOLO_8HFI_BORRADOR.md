# Protocolo 8HFI — borrador preregistrable para revisión

**Estado: PROPUESTA NO CONGELADA.** No autoriza ejecución. La calibración sigue bloqueada por la eliminación de iones, las condiciones históricas faltantes y los microestados no adjudicados. Ningún resultado de docking se consultó al redactar este protocolo.

## A. Receptor, caja e identidad

- Receptor candidato: PDB 8HFI, cadena A, NET humano P23975, inward-open, desipramina DSM A:701 en S1. Fuentes: curated_targets.json, objeto 8HFI desde línea 33267; https://www.rcsb.org/structure/8HFI.
- Caja del catálogo en Å: centro (100.281, 100.843, 101.442), tamaño (30.0, 30.0, 30.0), curated_targets.json, objeto 8HFI desde línea 33267.
- El mmCIF considerado es fuentes/8HFI.cif; su SHA-256 está en fuentes/manifest.json. Al congelar, verificar que el PDB consumido sea idéntico o fijar archivo y hash exactos.
- Receta del producto: RECEPTOR_RECIPE_VERSION=7 (backend/services/docking/preparer.py:796). El filtro elimina HETATM por defecto y conserva cofactores sólo con whitelist explícita (preparer.py:184, 292–319). El catálogo 8HFI no declara cofactores. MARGEN_SITIO_A=6.0 Å (preparer.py:856).
- Bloqueante: resolver y validar tratamiento de iones en NET. 8HFI no modela Na1, pero sí deposita Cl dentro de la caja; la ruta actual lo retira. Añadirlo a whitelist no prueba que los tipos/cargas y la interacción sean válidos con Vina/Meeko.
- No se declara hash del receptor preparado: no se ejecutó preparación. Hash de receta y PDBQT quedan pendientes de congelar estructura, iones, parámetros, runtime y código.

## B. Parámetros Vina propuestos

**Panel:** Vina 1.2.7, scoring vina, exhaustividad 32, seed 42, num_modes 9, CPU 1, según el protocolo candidato v2 en .worktrees/receptores-20261008/output/calibracion-20261008-panel-NET-v2/protocolo_previo.json. Ese archivo tiene estado CANDIDATE_PROTOCOL; no está congelado.

**Diferencia que requiere confirmación:** backend/core/config.py:112–115 declara exhaustividad estándar 8, exhaustividad de calibración 32, num_poses 5 y seed 42. El servicio vina_service.py:646, 653–669 pasa los valores explícitos y, si no recibe override, usa los defaults. El candidato v2 pide 32/9/42/1. Recomendación de este borrador: conservar el candidato 32/9/42/1 y pasarlo explícitamente; pedir al propietario/Claude que confirme 9 modos frente al default 5. El servicio revisado no consulta directamente vina_calibration_exhaustiveness al construir el comando; no asumir que 32 se aplica automáticamente.

**Redocking de DSM:** cinco corridas con seeds 42, 43, 44, 45 y 46, scoring vina, exhaustividad 32 y 9 modos explícitos. Semilla 42 es el default del producto y coincide con calibración; 43–46 son recomendación reproducible de este expediente, no default medido del producto.

## C. Verificación del ligando cristalográfico

1. Obtener la definición de componente CCD de desipramina DSM con su grafo y SMILES estereoquímico, sin usar coordenadas experimentales.
2. Generar un conformero 3D desde esa definición con RDKit ETKDG, semilla fija 42; añadir hidrógenos y optimizar sólo geometría intramolecular. No copiar la pose del mmCIF como inicio. Reservar coordenadas cristalográficas para evaluación posterior.
3. Después de docking, calcular RMSD simétrico de átomos pesados contra el cristal en el marco cartesiano original, sin superponer proteína ni ligando. Minimizar RMSD sobre automorfismos válidos de DSM. Registrar RMSD top-1 por semilla.
4. Verificado pasa sólo si RMSD top-1 ≤2.0 Å en al menos 3/5 seeds y PoseBusters no declara fallo bajo el protocolo MF-33-H-COR.
5. Para PoseBusters, regenerar hidrógenos desde los pesados dockeados y relajar sólo H manteniendo los pesados fijos. Aplicar los invariantes MF-33-H-COR: desplazamiento pesado máximo ≤1e−6 Å, SMILES canónico idéntico, carga formal idéntica, mismo número de enlaces y cero hidrógenos heredados del cristal (docs/papers/MF-33-H-COR.md:38–39). Registrar por separado cualquier violación.

## D. Panel, especies y congelación

- CSV por actividad: panel_8hfi.csv; SHA-256 provisional: d5c7a4bb4b117acd6d670fba3a0815f2e6de9ca697c2d4cb3c91625d9a6a7751, calculado el 2026-10-08. JSON asociado: SHA-256 fadca0d0953965f4d5cf5f67c4f61dc742866e834bb110dcd42a0691eb950856.
- Regla para actividad repetida del mismo padre: mediana pKi. El padre CHEMBL1182025 agrupa actividades 1716895 y 1716896; se retienen las 58 actividades fuente.
- Exclusiones propuestas: ninguna por estereoquímica parental ni por censura; n candidato=57. Las SMILES parentales neutras no son especies congeladas. Lista final de SMILES del microestado a acoplar y su hash siguen PENDIENTES.
- Antes de congelar adjuntar condiciones del assay (pH, temperatura, tampón, radioligando/Kd, fuente/constructo), decisión de microestado por compuesto, política Cl/Na/K, hash del CIF, receptor preparado y receta. Si no se recuperan condiciones, registrar el gap y pedir aceptación explícita de un protocolo de sensibilidad; no llenar valores por suposición.
- El hash anterior sólo identifica una tabla de fuente y transformaciones; no congela especies químicas ni es el hash final de calibración.

## E. Calibración

- Para cada padre elegible usar una especie química congelada y score top-1 con exhaustividad 32, seed 42 y 9 modos. No reoptimizar caja, estado, protocolo, pesos ni panel tras observar resultados.
- Convención: E_Vina es energía reportada; más negativa significa más favorable. Definir utilidad Q=−E_Vina, donde más alta es mejor. Correlación aprobatoria propuesta: Spearman(Q,pKi), con límite inferior IC95 >0. Publicar también rho(E_Vina,pKi), de signo esperado opuesto. Aceptar esta interpretación del signo antes de congelar.
- IC95 por bootstrap de cluster Murcko: 10,000 remuestreos, seed 42, percentiles 2.5/97.5, remuestreando clusters y manteniendo juntas sus moléculas; coincide con protocolo candidato v2. Hay cuatro clusters y uno contiene 53/57 padres, así que el intervalo es frágil. Si quedan menos de tres clusters, no emitir intervalo aprobatorio.
- Fallos: permitir una repetición técnica idéntica para error de infraestructura/archivo, dejando ambas en log. Si la molécula sigue sin score, el gate calibrado falla por panel incompleto. No quitarla del panel ni asignar score artificial. Publicar rho exploratorio de casos puntuables, n puntuable, fallos, n total=57, IC si interpretable y gráfica; no llamarlo aprobado.
- Potencia orientativa: para n=57 independientes, aproximación de Fisher z da rho mínimo tanh(1.96/sqrt(57−3))≈0.261 para límite inferior bilateral 95% >0. Ignora clusters; 53 de 57 en un cluster hace esta cifra optimista. El criterio final es bootstrap de clusters, no 0.261.

## F. Publicación pase lo que pase

Publicar Q, E_Vina, pKi, rho e IC95 con método/semilla, número de padres y actividades fuente, fallos, resultado redocking DSM, estado/tratamiento de iones, hashes de panel/ligandos/receptor/receta y gráfica score-pKi. Si falla un gate, etiquetar Demostración y mostrar resultados, sin cambiar receptor, panel o estado después de ver puntuaciones.

