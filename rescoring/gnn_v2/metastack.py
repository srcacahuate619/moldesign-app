"""
metastack.py — Stacking adaptativo automatico para N scorers.

Mapea (AUC_1, AUC_2, ..., AUC_N) -> (w_1, w_2, ..., w_N)
sin intervencion manual por familia o target.

Strategy: Softmax con temperatura T sobre AUCs elevados a potencia p.
  w_i = exp(T * AUC_i^p) / sum(exp(T * AUC_j^p))

Si T=0 -> equal weights
Si T=inf -> winner-take-all

La funcion calibrate encuentra T y p optimas dadas las AUCs de Phase 0.

Uso:
  from metastack import metastack_weights
  w = metastack_weights([auc_v, auc_x, auc_c, auc_d], T=6.0, p=1.0)
  
  # Backward-compatible:
  w_v, w_x, w_c, info = metastack_weights(auc_v, auc_x, auc_c)
"""
import numpy as np
from sklearn.metrics import roc_auc_score


def softmax_weights(scores, T=8.0, p=2.0):
    """Softmax from N scores with temperature T and power p."""
    scores = np.array(scores, dtype=np.float64)
    logits = T * (scores ** p)
    max_logit = logits.max()
    exp_logits = np.exp(logits - max_logit)
    w = exp_logits / exp_logits.sum()
    return list(w)


def metastack_weights(*args, T=6.0, p=1.0):
    """
    Compute adaptive stacking weights from individual AUCs.
    
    Flexible signature:
      metastack_weights(auc_v, auc_x, auc_c)          # 3 scorers (backward-compat)
      metastack_weights(auc_v, auc_x, auc_c, auc_d)   # 4 scorers
      metastack_weights([auc1, auc2, ...])            # N scorers
      metastack_weights([auc1, auc2, ...], T=..., p=...)
    
    Returns:
      w1, w2, ..., wN, info_dict   (for N=3: backward compat)
      or
      w_list, info_dict            (for N!=3)
    """
    # Parse args: could be list or individual AUCs
    if len(args) == 1 and isinstance(args[0], (list, tuple, np.ndarray)):
        aucs = list(args[0])
    else:
        aucs = list(args)

    aucs = np.array(aucs, dtype=np.float64)
    w = softmax_weights(aucs, T=T, p=p)

    # Saturation: if any scorer > 0.96, give it 80%
    max_auc = aucs.max()
    if max_auc >= 0.96:
        idx = np.argmax(aucs)
        w_arr = np.zeros(len(aucs))
        w_arr[idx] = 0.8
        rest = aucs.copy()
        rest[idx] = 0
        if rest.sum() > 0:
            for j in range(len(aucs)):
                if j != idx:
                    w_arr[j] = 0.2 * (rest[j] / rest.sum())
        w = list(w_arr)

    # If ALL bad (< 0.65), uniform hedge
    if max_auc < 0.65:
        w = [1.0 / len(aucs)] * len(aucs)

    info = {
        "aucs": {f"scorer_{i}": float(aucs[i]) for i in range(len(aucs))},
        "params": {"T": T, "p": p},
        "winner": int(np.argmax(aucs)),
        "max_auc": float(max_auc),
    }

    # Backward-compatible: if 3 AUCs, return (w_v, w_x, w_c, info)
    if len(aucs) == 3:
        return float(w[0]), float(w[1]), float(w[2]), info
    # For N scorers, return (w_list, info)
    return [float(x) for x in w], info


def optimal_weights(target_data):
    """Grid search optimal weights for target with {labels, scores: [s1, s2, ...]}."""
    labels = target_data["labels"]
    score_arrays = target_data["scores"]
    n = len(score_arrays)

    best_auc = 0.0
    best_w = None
    step = 0.05

    def _recursive_weight_search(idx, remaining_weight):
        """Recursive grid search for any N."""
        nonlocal best_auc, best_w
        if idx == n - 1:
            w = [0.0] * n
            # This depth-first approach is O((1/step)^(n-1)) — fine for n<=5
            pass
        return

    # For efficiency, use fixed step for n<=4
    # n=3: standard double loop
    if n == 3:
        for w0 in np.arange(0, 1.01, step):
            for w1 in np.arange(0, 1.01 - w0, step):
                w2 = 1.0 - w0 - w1
                if w2 < 0: continue
                composite = w0 * score_arrays[0] + w1 * score_arrays[1] + w2 * score_arrays[2]
                auc = roc_auc_score(labels, composite)
                if auc > best_auc:
                    best_auc = auc
                    best_w = [round(w0, 3), round(w1, 3), round(w2, 3)]
    elif n == 4:
        for w0 in np.arange(0, 1.01, step):
            for w1 in np.arange(0, 1.01 - w0, step):
                for w2 in np.arange(0, 1.01 - w0 - w1, step):
                    w3 = 1.0 - w0 - w1 - w2
                    if w3 < 0: continue
                    composite = w0 * score_arrays[0] + w1 * score_arrays[1] + w2 * score_arrays[2] + w3 * score_arrays[3]
                    auc = roc_auc_score(labels, composite)
                    if auc > best_auc:
                        best_auc = auc
                        best_w = [round(w0, 3), round(w1, 3), round(w2, 3), round(w3, 3)]

    return best_w, best_auc


def calibrate(targets, T_candidates=None, p_candidates=None):
    """Find best (T, p) across all targets to minimize MSE to optimal weights."""
    if T_candidates is None:
        T_candidates = np.arange(0, 21, 1)
    if p_candidates is None:
        p_candidates = [1.0, 1.5, 2.0, 2.5, 3.0]

    best_err = float("inf")
    best_params = None
    results = []

    for T in T_candidates:
        for p in p_candidates:
            total_mse = 0.0
            for name, t in targets.items():
                labels = t["labels"]
                score_arrays = t["scores"]
                n = len(score_arrays)

                # Individual AUCs
                aucs = [float(roc_auc_score(labels, s)) for s in score_arrays]

                # Predicted weights
                w_pred, _ = metastack_weights(aucs, T=T, p=p)

                # Optimal weights
                opt_w, opt_auc = optimal_weights(t)

                if opt_w is None:
                    continue

                # MSE
                mse = sum((w_pred[i] - opt_w[i])**2 for i in range(n))
                total_mse += mse

            mean_mse = total_mse / len(targets)
            if mean_mse < best_err:
                best_err = mean_mse
                best_params = (T, p)

            results.append({"T": T, "p": p, "mse": mean_mse})

    return best_params, best_err, results
