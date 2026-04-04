from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import math
import sys

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODELS_ROOT = PROJECT_ROOT.parent / "Models"
if str(MODELS_ROOT) not in sys.path:
    sys.path.append(str(MODELS_ROOT))

try:
    from utils.constants import V_COLS, C_COLS, D_COLS, M_COLS  # type: ignore
except Exception:
    V_COLS, C_COLS, D_COLS, M_COLS = [], [], [], []

try:
    import shap  # type: ignore
except Exception:  # pragma: no cover
    shap = None


@dataclass
class InferenceOutput:
    model_decision: str
    calibrated_prob: float
    stacker_score: float
    base_outputs: dict[str, float]
    queue_outputs: dict[str, float]
    why_flagged: str


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _decision_from_prob(prob: float) -> str:
    if prob >= 0.75:
        return "block"
    if prob >= 0.4:
        return "mfa"
    return "approve"


def _feature_vector(feature_map: dict[str, float]) -> tuple[np.ndarray, list[str]]:
    names = ["amt_zscore", "delta_t_norm", "device_novelty", "device_dist_score", "M_fail_count", "txn_rank_norm"]
    return np.array([feature_map[n] for n in names], dtype=np.float32), names


def _manual_shap_like(features: np.ndarray, feature_names: list[str], weights: np.ndarray) -> list[tuple[str, float]]:
    impacts = features * weights
    order = np.argsort(np.abs(impacts))[::-1]
    return [(feature_names[idx], float(impacts[idx])) for idx in order]


def _try_shap_explain(features: np.ndarray, feature_names: list[str], weights: np.ndarray, bias: float) -> list[tuple[str, float]]:
    if shap is None:
        return _manual_shap_like(features, feature_names, weights)

    try:
        def model_fn(x: np.ndarray) -> np.ndarray:
            logits = x @ weights + bias
            return 1.0 / (1.0 + np.exp(-logits))

        background = np.zeros((1, features.shape[0]), dtype=np.float32)
        explainer = shap.Explainer(model_fn, background)
        explanation = explainer(np.array([features], dtype=np.float32))
        values = np.array(explanation.values)[0]
        order = np.argsort(np.abs(values))[::-1]
        return [(feature_names[idx], float(values[idx])) for idx in order]
    except Exception:
        return _manual_shap_like(features, feature_names, weights)


def _render_explanation(
    top_impacts: list[tuple[str, float]],
    amount: float,
    location: str,
    known_device: bool,
    decision: str,
) -> str:
    pretty = {
        "amt_zscore": "amount anomaly",
        "delta_t_norm": "unusual transaction timing",
        "device_novelty": "new device signal",
        "device_dist_score": "device embedding distance",
        "M_fail_count": "recent failed attempts",
        "txn_rank_norm": "transaction velocity",
    }

    top = [pretty.get(name, name) for name, _ in top_impacts[:3]]
    device_phrase = "a known device" if known_device else "an unrecognized device"

    if decision == "block":
        action = "Recommend immediate block and temporary account freeze."
    elif decision == "mfa":
        action = "Recommend step-up authentication and analyst review."
    else:
        action = "Risk appears controlled; approve with monitoring."

    amount_inr = f"₹{amount:,.0f}"
    return (
        f"Critical: Transaction of {amount_inr} from {device_phrase} in {location} was flagged due to "
        f"{', '.join(top)}. Pattern is consistent with account takeover risk. {action}"
    )


def run_inference(
    *,
    amount: float,
    delta_t_norm: float,
    amt_zscore: float,
    m_fail_count: int,
    txn_rank: int,
    device_novelty: float,
    device_dist_score: float,
    location: str,
    known_device: bool,
) -> InferenceOutput:
    # LightGBM-style linear blend inspired by Model H stacker inputs.
    feature_map = {
        "amt_zscore": float(min(6.0, max(0.0, amt_zscore))),
        "delta_t_norm": float(min(1.0, max(0.0, delta_t_norm))),
        "device_novelty": float(min(1.0, max(0.0, device_novelty))),
        "device_dist_score": float(min(1.0, max(0.0, device_dist_score))),
        "M_fail_count": float(min(10, max(0, m_fail_count))),
        "txn_rank_norm": float(min(1.0, txn_rank / 200.0)),
    }

    features, feature_names = _feature_vector(feature_map)
    weights = np.array([0.34, 0.27, 0.33, 0.22, 0.11, 0.08], dtype=np.float32)
    bias = -1.15

    logit = float(features @ weights + bias)
    stacker_score = float(min(1.0, max(0.0, _sigmoid(logit))))
    calibrated_prob = float(min(1.0, max(0.0, 0.04 + 0.92 * stacker_score)))
    model_decision = _decision_from_prob(calibrated_prob)

    seq_anomaly_score = float(min(1.0, 0.45 * feature_map["amt_zscore"] / 3.0 + 0.55 * feature_map["delta_t_norm"]))
    ato_prob = float(min(1.0, 0.55 * feature_map["device_novelty"] + 0.45 * feature_map["device_dist_score"]))
    synth_id_prob = float(min(1.0, 0.35 * feature_map["M_fail_count"] / 5.0 + 0.35 * feature_map["device_novelty"] + 0.3 * feature_map["txn_rank_norm"]))
    recon_error = float(0.4 + 2.6 * seq_anomaly_score)
    tabnet_logit = float(-2.1 + 4.6 * ato_prob)
    gnn_logit = float(-2.4 + 4.0 * feature_map["device_dist_score"])

    top_impacts = _try_shap_explain(features, feature_names, weights, bias)
    why_flagged = _render_explanation(top_impacts, amount, location, known_device, model_decision)

    return InferenceOutput(
        model_decision=model_decision,
        calibrated_prob=round(calibrated_prob, 6),
        stacker_score=round(stacker_score, 6),
        base_outputs={
            "gnn_logit": round(gnn_logit, 6),
            "device_dist_score": round(feature_map["device_dist_score"], 6),
        },
        queue_outputs={
            "seq_anomaly_score": round(seq_anomaly_score, 6),
            "synth_id_prob": round(synth_id_prob, 6),
            "ato_prob": round(ato_prob, 6),
            "recon_error": round(recon_error, 6),
            "tabnet_logit": round(tabnet_logit, 6),
        },
        why_flagged=why_flagged,
    )
