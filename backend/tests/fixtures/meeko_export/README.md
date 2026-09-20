# Salidas reales de `mk_export`

Archivos **generados por los programas de verdad**, no escritos a mano. Existen
porque el defecto que cubren sobrevivió precisamente a las pruebas con
cabeceras inventadas: `parse_vina_output_sdf` documentaba `> <meeko>`, que
ningún programa emite, mientras Meeko escribe `>  <meeko>  (1) ` y el parser lo
descartaba. Ver `backend/tests/test_lector_de_sdf_de_meeko.py`.

**No los edites a mano.** Un byte cambiado aquí convierte al guardián en prosa.

## Procedencia

Generados el **2026-09-19** en `D:\moldesign-build` con el runtime distribuido
(`python-embed`, 3.11.9) y el Vina empaquetado:

- Vina 1.2.7, `tools/vina/vina.exe`,
  SHA-256 `e0c4b2715e0c1a74f6e92d0f3be0328ac97542eafbc111e6b1efad897a73cce5`
- Receptor `scripts/artifacts_science/REC-07/_work/5TUN_receptor.pdbqt`,
  SHA-256 `eceefe6d18ff716ad30d30a6bb3b267133c2ccf9b10b92d8c0f196e79cc0665f`
- Caja: centro `(11.104, 135.221, 21.288)`, tamaño `(19.0, 25.3, 25.9)`, semilla `42`
- Export: `python -m meeko.cli.mk_export <out.pdbqt> -s <out.sdf>`

| Archivo | Qué es |
|---|---|
| `paracetamol_9_poses.pdbqt` | salida de Vina, `--exhaustiveness 8 --num_modes 9` |
| `paracetamol_9_poses.sdf` | `mk_export` sobre el anterior: 9 registros, cada uno con su propiedad `meeko` |
| `exaltolida_macrociclo.pdbqt` | salida de Vina, `--exhaustiveness 4 --num_modes 3` |
| `exaltolida_macrociclo.sdf` | `mk_export` sobre el anterior: el macrociclo con su anillo cerrado |
| `exaltolida_conformero_de_entrada.sdf` | el confórmero que entró a Vina, para comparar composición |

Los ligandos de entrada salieron de `ENS-PILOT-01`, preparados por
`meeko.cli.mk_prepare_ligand`. **No es un redocking**: los ligandos no son los
nativos de 5TUN y ninguna afinidad de aquí es interpretable como ciencia. Se
conservan porque lo que se prueba es el formato y la procedencia, no el número.

## Dos rarezas que se conservan a propósito

1. **Los `.pdbqt` traen bytes NUL.** Nueve líneas completas de 23 NUL cada una en
   `paracetamol_9_poses.pdbqt` (una por pose); los escribe Vina. Decodifican bien
   en UTF-8 estricto y no casan con ningún parser. Están aquí para que la prueba
   vea lo que ve producción, no una versión limpiada.
2. **Terminaciones CRLF.** También de Vina y de `mk_export` en Windows. Se
   conservan porque `.gitattributes` ya marca `*.sdf` y `*.pdbqt` como `-text`,
   así que git nunca reescribe estos bytes. Si esa regla se retirara, la fixture
   dejaría de ser la salida real y la prueba dejaría de demostrar lo que dice.
