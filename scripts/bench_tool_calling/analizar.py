"""Compara los brazos y emite la tabla, con las condiciones de cada número."""
import json, os, statistics as st
from collections import defaultdict

AQUI = os.path.dirname(os.path.abspath(__file__))


def cargar(nombre):
    p = os.path.join(AQUI, nombre)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []


def pct(n, d):
    return f"{100*n/d:5.1f}%" if d else "  n/a"


def resumen(filas, etiqueta):
    """Desglose por las dos variables del diseño 2x2."""
    print(f"\n{'='*78}\n{etiqueta}   (n={len(filas)})\n{'='*78}")
    print(f"{'q':3s} {'desc':5s} {'n':>3s}  {'acierto':>8s}  {'en alcance':>11s}  "
          f"{'abstencion':>11s}  {'falso positivo':>14s}  {'ms p50':>7s}")
    print("-" * 78)
    for iq in ("es", "en"):
        for idsc in ("es", "en"):
            sub = [f for f in filas if f["idioma_q"] == iq and f["idioma_desc"] == idsc]
            if not sub:
                continue
            dentro = [f for f in sub if f["esperado"] is not None]
            fuera = [f for f in sub if f["esperado"] is None]
            ac = sum(f["acierto_tool"] for f in sub)
            ac_d = sum(f["acierto_tool"] for f in dentro)
            abst = sum(1 for f in fuera if f["obtenido"] is None)
            fp = sum(1 for f in fuera if f["obtenido"] is not None)
            ms = sorted(f["ms"] for f in sub)
            print(f"{iq:3s} {idsc:5s} {len(sub):3d}  {pct(ac,len(sub)):>8s}  "
                  f"{pct(ac_d,len(dentro)):>11s}  {pct(abst,len(fuera)):>11s}  "
                  f"{fp:>3d}/{len(fuera):<10d}  {ms[len(ms)//2]:7.0f}")


def falsos_positivos(filas, etiqueta):
    """Lo peor que puede pasar: llamada a herramienta en peticion fuera de alcance."""
    malos = [f for f in filas if f["esperado"] is None and f["obtenido"] is not None]
    if not malos:
        print(f"\n{etiqueta}: ningun falso positivo.")
        return
    print(f"\n{etiqueta}: {len(malos)} falsos positivos (herramienta invocada fuera de alcance)")
    for f in sorted(malos, key=lambda x: -(x["confidence"] or 0))[:10]:
        c = f"conf={f['confidence']:.2f}" if f["confidence"] is not None else "conf=n/a"
        print(f"   q={f['idioma_q']} d={f['idioma_desc']} [{c}] "
              f"{f['prompt'][:46]:46s} -> {f['obtenido']}  {f['args']}")


def main():
    needle = cargar("resultados_needle.json")
    qwen = cargar("resultados_qwen.json")

    for filas, et in ((needle, "NEEDLE 3 (29-121M, 2-bit, CPU)"),
                      (qwen, "QWEN2.5-1.5B-INSTRUCT Q4_K_M (llama-server CUDA)")):
        if filas:
            resumen(filas, et)

    for filas, et in ((needle, "Needle"), (qwen, "Qwen")):
        if filas:
            falsos_positivos(filas, et)

    # Comparacion directa en la condicion del producto: pregunta ES, descripcion ES.
    print(f"\n{'='*78}\nLA CONDICION DEL PRODUCTO: pregunta en espanol, descripcion en espanol\n{'='*78}")
    print(f"{'brazo':14s} {'acierto':>8s} {'en alcance':>11s} {'abstencion':>11s} "
          f"{'falsos pos':>11s} {'ms p50':>8s} {'ms p95':>8s}")
    print("-" * 78)
    for filas, et in ((needle, "Needle 3"), (qwen, "Qwen2.5-1.5B")):
        sub = [f for f in filas if f["idioma_q"] == "es" and f["idioma_desc"] == "es"]
        if not sub:
            continue
        dentro = [f for f in sub if f["esperado"] is not None]
        fuera = [f for f in sub if f["esperado"] is None]
        ms = sorted(f["ms"] for f in sub)
        print(f"{et:14s} {pct(sum(f['acierto_tool'] for f in sub),len(sub)):>8s} "
              f"{pct(sum(f['acierto_tool'] for f in dentro),len(dentro)):>11s} "
              f"{pct(sum(1 for f in fuera if f['obtenido'] is None),len(fuera)):>11s} "
              f"{sum(1 for f in fuera if f['obtenido'] is not None):>4d}/{len(fuera):<6d} "
              f"{ms[len(ms)//2]:8.0f} {ms[int(len(ms)*0.95)-1]:8.0f}")

    # Recursos declarados por el propio motor de Needle.
    ram = [f["peak_ram_mb"] for f in needle if f.get("peak_ram_mb")]
    if ram:
        print(f"\nNeedle peak_ram_mb (reportado por el motor): "
              f"min {min(ram):.0f}  max {max(ram):.0f}")
    pre = [f["prefill_tps"] for f in needle if f.get("prefill_tps")]
    dec = [f["decode_tps"] for f in needle if f.get("decode_tps")]
    if pre:
        print(f"Needle prefill_tps p50 {st.median(pre):.0f}   decode_tps p50 {st.median(dec):.0f}")


if __name__ == "__main__":
    main()
