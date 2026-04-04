from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import importlib.util
import re
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODELS_ROOT = PROJECT_ROOT.parent / "Models"
PIPELINE_FILE = MODELS_ROOT / "run_pipeline_phase_refactored.py"

INDIAN_LOCATIONS = [
    "Mumbai",
    "Delhi",
    "Bengaluru",
    "Hyderabad",
    "Chennai",
    "Kolkata",
    "Pune",
    "Ahmedabad",
    "Jaipur",
    "Lucknow",
]


@dataclass
class ModelRowContext:
    transaction_amt: float
    merchant_name: str
    location: str
    card1: int | None
    d1: float | None
    d2: float | None
    d3: float | None
    v_cols: list[float]
    c_cols: list[float]
    m_cols: list[int]
    raw_fraud_score: float
    calibrated_prob: float
    decision: str
    source_transaction_id: str


def _load_feature_store() -> pd.DataFrame | None:
    candidates = [
        MODELS_ROOT / "features" / "feature_store.parquet",
        MODELS_ROOT / "data" / "processed" / "ieee_cis_fully_enriched.parquet",
    ]
    for path in candidates:
        if path.exists():
            try:
                return pd.read_parquet(path)
            except Exception:
                continue
    return None


def _load_pipeline_module() -> Any | None:
    if not PIPELINE_FILE.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("run_pipeline_phase_refactored", str(PIPELINE_FILE))
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


def _extract_series_values(row: dict[str, Any], pattern: str, cast: Any) -> list[Any]:
    regex = re.compile(pattern)
    pairs: list[tuple[int, Any]] = []
    for key, value in row.items():
        match = regex.fullmatch(str(key))
        if not match:
            continue
        idx = int(match.group(1))
        try:
            pairs.append((idx, cast(value if value is not None else 0)))
        except Exception:
            pairs.append((idx, cast(0)))
    pairs.sort(key=lambda x: x[0])
    return [v for _, v in pairs]


def _default_decision_from_prob(prob: float) -> str:
    if prob < 0.30:
        return "approve"
    if prob < 0.70:
        return "mfa"
    return "block"


def _random_indian_location() -> str:
    return str(np.random.choice(INDIAN_LOCATIONS))


def generate_model_row_context() -> ModelRowContext:
    df = _load_feature_store()
    if df is None or df.empty:
        amount = float(np.random.uniform(50.0, 5000.0))
        prob = float(np.random.uniform(0.01, 0.99))
        return ModelRowContext(
            transaction_amt=round(amount, 2),
            merchant_name="Model Feed Merchant",
            location=_random_indian_location(),
            card1=None,
            d1=None,
            d2=None,
            d3=None,
            v_cols=[],
            c_cols=[],
            m_cols=[],
            raw_fraud_score=prob,
            calibrated_prob=prob,
            decision=_default_decision_from_prob(prob),
            source_transaction_id="MODEL_FALLBACK",
        )

    module = _load_pipeline_module()
    working_df = df.copy()

    sampled_row = None
    if module is not None and hasattr(module, "get_random_live_transaction"):
        try:
            sampled_row = module.get_random_live_transaction(working_df)
        except Exception:
            sampled_row = None

    if sampled_row is None:
        sampled_row = working_df.sample(n=1).iloc[0].to_dict()

    sampled_df = pd.DataFrame([sampled_row])
    if "isFraud" not in sampled_df.columns:
        sampled_df["isFraud"] = 0

    eval_df = pd.concat([working_df.tail(5000), sampled_df], ignore_index=True, sort=False)
    eval_df = eval_df.fillna(0)

    if module is not None and hasattr(module, "test_full_pipeline") and hasattr(module, "PipelineConfig"):
        try:
            module.test_full_pipeline(eval_df, module.PipelineConfig())
        except Exception:
            # Fall back to local thresholding if full pipeline eval raises metric errors.
            pass

    out_row = eval_df.iloc[-1].to_dict()

    raw_score = float(out_row.get("raw_fraud_score", out_row.get("tabnet_logit", 0.0)))
    if raw_score < 0 or raw_score > 1:
        raw_score = float(1 / (1 + np.exp(-raw_score)))

    calibrated_prob = float(out_row.get("calibrated_prob", raw_score))
    decision = str(out_row.get("decision", _default_decision_from_prob(calibrated_prob))).lower()

    merchant_name = str(
        out_row.get("merchant_name")
        or out_row.get("Merchant")
        or out_row.get("merchant")
        or "Model Feed Merchant"
    )
    location = str(
        out_row.get("location")
        or out_row.get("addr1")
        or out_row.get("city")
        or _random_indian_location()
    )
    if location.strip().lower() in {"model feed location", "unknown", "na", "n/a"}:
        location = _random_indian_location()

    v_cols = _extract_series_values(out_row, r"V(\d+)", float)
    c_cols = _extract_series_values(out_row, r"C(\d+)", float)
    m_cols = _extract_series_values(out_row, r"M(\d+)", int)

    return ModelRowContext(
        transaction_amt=round(float(out_row.get("TransactionAmt", np.random.uniform(50.0, 5000.0))), 2),
        merchant_name=merchant_name,
        location=location,
        card1=int(out_row["card1"]) if "card1" in out_row and out_row["card1"] not in (None, "") else None,
        d1=float(out_row["D1"]) if "D1" in out_row else None,
        d2=float(out_row["D2"]) if "D2" in out_row else None,
        d3=float(out_row["D3"]) if "D3" in out_row else None,
        v_cols=v_cols,
        c_cols=c_cols,
        m_cols=m_cols,
        raw_fraud_score=round(raw_score, 6),
        calibrated_prob=round(calibrated_prob, 6),
        decision=decision,
        source_transaction_id=str(out_row.get("TransactionID", "MODEL_SOURCE_TXN")),
    )
