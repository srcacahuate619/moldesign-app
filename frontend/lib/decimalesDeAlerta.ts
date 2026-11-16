// Los decimales que hacen falta para que un valor y su corte no se escriban igual.
//
// Espejo de `decimales_para_distinguir` en `backend/services/docking/selectivity.py` (revisión final de 1.0.4,
// caso hERG). La alerta usa una desigualdad estricta (`aff < umbral`) y con un decimal fijo −7,004 frente a −7,0
// salía «−7,0 kcal/mol rebasó el umbral crítico (−7,0 kcal/mol)»: la comparación era correcta y la frase, ilegible.
// La desigualdad no cambia; sólo se escribe con la precisión que deja ver por qué se cumple. Con un valor lejos del
// corte (el caso normal) son el mismo decimal de siempre.

export function decimalesParaDistinguir(
  valor: number,
  corte: number,
  minimo = 1,
  maximo = 6,
): number {
  for (let decimales = minimo; decimales <= maximo; decimales++) {
    if (valor.toFixed(decimales) !== corte.toFixed(decimales)) return decimales;
  }
  return maximo;
}

/** Valor y corte escritos con los mismos decimales, los mínimos que los distinguen. */
export function valorYCorte(valor: number, corte: number): { valor: string; corte: string } {
  const d = decimalesParaDistinguir(valor, corte);
  return { valor: valor.toFixed(d), corte: corte.toFixed(d) };
}
