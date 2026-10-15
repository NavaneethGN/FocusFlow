"""
backend/hlr/evaluation.py
Comprehensive, leakage-safe evaluation engine for HLR models and baselines.
Pure Python + standard math. No database, HTTP, FastAPI or external framework dependencies.

ASSUMPTION: Baselines are evaluated on the identical set of examples as candidate models.
All metrics explicitly document the prediction target ("p_observed" or "h_target").
"""
from dataclasses import dataclass, field
import math
import random
from typing import Sequence, List, Dict, Any, Optional, Tuple

from .config import HLRConfig
from .features import RAW_SPEC, SQRT_SPEC, ConceptCounts, extract_features
from .predictor import HLRValidationError, predict_half_life, predict_recall
from .updater import ModelArtifact, HLR_V0_FIXED

@dataclass
class MetricSummary:
    """A metric value accompanied by a student-resampled bootstrap confidence interval."""
    name: str
    target: str
    value: float
    ci_95_lower: Optional[float] = None
    ci_95_upper: Optional[float] = None

@dataclass
class CalibrationBin:
    bin_index: int
    bin_lower: float
    bin_upper: float
    count: int
    mean_predicted: float
    mean_observed: float
    calibration_error: float

@dataclass
class ModelEvaluationReport:
    model_name: str
    n_examples: int
    metrics: Dict[str, MetricSummary]
    calibration_table: List[CalibrationBin]
    history_breakdown: Dict[str, Dict[str, float]]
    delta_breakdown: Dict[str, Dict[str, float]]

@dataclass
class ComparisonReport:
    """Full evaluation and baseline comparison report."""
    n_examples: int
    models: Dict[str, ModelEvaluationReport]
    baselines: Dict[str, ModelEvaluationReport]
    timestamp_utc: str

def compute_mae(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    """Mean Absolute Error."""
    if len(y_true) != len(y_pred):
        raise HLRValidationError("Length mismatch in compute_mae")
    if len(y_true) == 0:
        return 0.0
    return sum(abs(t - p) for t, p in zip(y_true, y_pred)) / len(y_true)

def compute_rmse(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    """Root Mean Squared Error."""
    if len(y_true) != len(y_pred):
        raise HLRValidationError("Length mismatch in compute_rmse")
    if len(y_true) == 0:
        return 0.0
    mse = sum((t - p) ** 2 for t, p in zip(y_true, y_pred)) / len(y_true)
    return math.sqrt(mse)

def compute_pearson_correlation(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
    """Pearson correlation coefficient r."""
    if len(x) != len(y):
        raise HLRValidationError("Length mismatch in compute_pearson_correlation")
    n = len(x)
    if n < 2:
        return None
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    var_x = sum((xi - mean_x) ** 2 for xi in x)
    var_y = sum((yi - mean_y) ** 2 for yi in y)
    if var_x < 1e-12 or var_y < 1e-12:
        return 0.0
    cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    return cov / math.sqrt(var_x * var_y)

def is_binary_labels(labels: Sequence[float]) -> bool:
    """Checks whether all labels are strictly 0.0 or 1.0 (binary recall outcomes)."""
    return all(abs(l - 0.0) < 1e-9 or abs(l - 1.0) < 1e-9 for l in labels)

def compute_brier_score(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    """Brier score: strictly for binary outcomes."""
    if not is_binary_labels(y_true):
        raise HLRValidationError("Brier score only supported for binary labels (refused on fractional labels)")
    return compute_rmse(y_true, y_pred) ** 2

def compute_auc(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    """Receiver Operating Characteristic AUC via Mann-Whitney U rank statistic."""
    if not is_binary_labels(y_true):
        raise HLRValidationError("AUC only supported for binary labels (refused on fractional labels)")
    
    positives = [p for t, p in zip(y_true, y_pred) if abs(t - 1.0) < 1e-9]
    negatives = [p for t, p in zip(y_true, y_pred) if abs(t - 0.0) < 1e-9]

    n_pos = len(positives)
    n_neg = len(negatives)
    if n_pos == 0 or n_neg == 0:
        return 0.5  # Undefined single-class baseline

    # Pairwise comparison with tie-breaking
    wins = 0.0
    for pos in positives:
        for neg in negatives:
            if pos > neg:
                wins += 1.0
            elif abs(pos - neg) < 1e-9:
                wins += 0.5

    return wins / (n_pos * n_neg)

def compute_calibration_table(
    y_true: Sequence[float],
    y_pred: Sequence[float],
    n_bins: int = 10
) -> List[CalibrationBin]:
    """Builds calibration bins over predicted probabilities in [0, 1]."""
    bins = []
    bin_width = 1.0 / n_bins
    for b_idx in range(n_bins):
        b_low = b_idx * bin_width
        b_high = (b_idx + 1) * bin_width
        # Include high edge in last bin
        bin_pairs = [
            (t, p) for t, p in zip(y_true, y_pred)
            if (b_low <= p < b_high) or (b_idx == n_bins - 1 and abs(p - 1.0) < 1e-9)
        ]
        count = len(bin_pairs)
        if count > 0:
            mean_p = sum(p for _, p in bin_pairs) / count
            mean_obs = sum(t for t, _ in bin_pairs) / count
            cal_err = abs(mean_p - mean_obs)
        else:
            mean_p = (b_low + b_high) / 2.0
            mean_obs = 0.0
            cal_err = 0.0

        bins.append(CalibrationBin(
            bin_index=b_idx,
            bin_lower=b_low,
            bin_upper=b_high,
            count=count,
            mean_predicted=mean_p,
            mean_observed=mean_obs,
            calibration_error=cal_err
        ))
    return bins

def _bootstrap_metric_ci(
    student_examples: Dict[str, List[Tuple[float, float]]],
    metric_fn: Any,
    n_bootstraps: int = 100,
    seed: int = 42
) -> Tuple[float, float]:
    """Computes 95% bootstrap confidence interval resampled clustered by student."""
    students = list(student_examples.keys())
    if len(students) < 2:
        return (0.0, 0.0)

    rng = random.Random(seed)
    scores: List[float] = []

    for _ in range(n_bootstraps):
        resampled_students = [rng.choice(students) for _ in range(len(students))]
        y_t: List[float] = []
        y_p: List[float] = []
        for s in resampled_students:
            for t_val, p_val in student_examples[s]:
                y_t.append(t_val)
                y_p.append(p_val)
        if len(y_t) > 0:
            scores.append(metric_fn(y_t, y_p))

    if len(scores) == 0:
        return (0.0, 0.0)

    scores.sort()
    low_idx = int(math.floor(0.025 * len(scores)))
    high_idx = int(math.ceil(0.975 * len(scores))) - 1
    high_idx = max(0, min(high_idx, len(scores) - 1))
    return scores[low_idx], scores[high_idx]

def evaluate_single_predictor(
    predictions: Sequence[Tuple[float, float, float, float, str]],
    model_name: str,
    n_bootstraps: int = 100
) -> ModelEvaluationReport:
    """Evaluates a list of predictions: (y_true, y_pred, h_target, h_pred, student_id)."""
    y_true = [item[0] for item in predictions]
    y_pred = [item[1] for item in predictions]
    h_target = [item[2] for item in predictions]
    h_pred = [item[3] for item in predictions]

    n_examples = len(predictions)
    mae_val = compute_mae(y_true, y_pred)
    rmse_val = compute_rmse(y_true, y_pred)
    corr_val = compute_pearson_correlation(h_target, h_pred) or 0.0

    # Group by student for clustered bootstrap
    student_pairs: Dict[str, List[Tuple[float, float]]] = {}
    for item in predictions:
        s_id = item[4]
        if s_id not in student_pairs:
            student_pairs[s_id] = []
        student_pairs[s_id].append((item[0], item[1]))

    mae_low, mae_high = _bootstrap_metric_ci(student_pairs, compute_mae, n_bootstraps)
    rmse_low, rmse_high = _bootstrap_metric_ci(student_pairs, compute_rmse, n_bootstraps)

    metrics = {
        "mae": MetricSummary("MAE", "p_observed", mae_val, mae_low, mae_high),
        "rmse": MetricSummary("RMSE", "p_observed", rmse_val, rmse_low, rmse_high),
        "half_life_correlation": MetricSummary("Pearson_r", "h_target", corr_val)
    }

    # Binary metrics if labels are purely binary
    if is_binary_labels(y_true) and n_examples > 0:
        auc_val = compute_auc(y_true, y_pred)
        brier_val = compute_brier_score(y_true, y_pred)
        metrics["auc"] = MetricSummary("AUC", "p_observed", auc_val)
        metrics["brier"] = MetricSummary("Brier", "p_observed", brier_val)

    cal_table = compute_calibration_table(y_true, y_pred)

    return ModelEvaluationReport(
        model_name=model_name,
        n_examples=n_examples,
        metrics=metrics,
        calibration_table=cal_table,
        history_breakdown={},
        delta_breakdown={}
    )

def evaluate_models(
    models: Dict[str, ModelArtifact],
    examples: Sequence[Any],
    train_mean_p: Optional[float] = None,
    n_bootstraps: int = 100
) -> ComparisonReport:
    """Evaluates candidate models and standard baselines on the IDENTICAL set of examples."""
    if len(examples) == 0:
        raise HLRValidationError("Cannot evaluate models on empty examples")

    # Extract observed labels, deltas, and concept counts
    extracted_data = []
    all_p = []
    for ex in examples:
        if isinstance(ex, dict):
            p = float(ex["p_observed"])
            delta = float(ex["delta_days"])
            x_raw = ex.get("x_before", [1.0, 0.0, 0.0])
            counts_before = ex.get("counts_before", {"n_right": 0, "n_wrong": 0})
            s_id = str(ex.get("student_id", "std-unknown"))
        else:
            p = float(getattr(ex, "p_observed"))
            delta = float(getattr(ex, "delta_days"))
            x_raw = getattr(ex, "x_before")
            counts_before = getattr(ex, "counts_before", {"n_right": 0, "n_wrong": 0})
            s_id = str(getattr(ex, "student_id", "std-unknown"))

        # Compute empirical target half-life
        p_clipped = min(max(p, 0.0001), 0.9999)
        h_target = min(max(-delta / math.log2(p_clipped), 15.0 / 1440.0), 270.0)

        nr = counts_before.get("n_right", 0)
        nw = counts_before.get("n_wrong", 0)
        counts = ConceptCounts(nr, nw)

        extracted_data.append({
            "p": p,
            "delta": delta,
            "counts": counts,
            "h_target": h_target,
            "student_id": s_id
        })
        all_p.append(p)

    default_train_mean = sum(all_p) / len(all_p) if train_mean_p is None else train_mean_p

    # 1. Evaluate Candidate Models
    model_reports: Dict[str, ModelEvaluationReport] = {}
    for m_name, artifact in models.items():
        preds = []
        for row in extracted_data:
            x_feat = extract_features(row["counts"], artifact.feature_spec)
            h = predict_half_life(artifact.theta, x_feat, artifact.config)
            p_hat = predict_recall(h, row["delta"], artifact.config)
            preds.append((row["p"], p_hat, row["h_target"], h, row["student_id"]))
        model_reports[m_name] = evaluate_single_predictor(preds, m_name, n_bootstraps)

    # 2. Evaluate Baselines
    baseline_reports: Dict[str, ModelEvaluationReport] = {}

    # Baseline 1: Leitner fixed model (hlr_v0_fixed)
    leitner_preds = []
    for row in extracted_data:
        x_raw = extract_features(row["counts"], RAW_SPEC)
        h = predict_half_life(HLR_V0_FIXED.theta, x_raw, HLR_V0_FIXED.config)
        p_hat = predict_recall(h, row["delta"], HLR_V0_FIXED.config)
        leitner_preds.append((row["p"], p_hat, row["h_target"], h, row["student_id"]))
    baseline_reports["hlr_v0_fixed"] = evaluate_single_predictor(leitner_preds, "hlr_v0_fixed", n_bootstraps)

    # Baseline 2: Constant Probability (train mean)
    constant_preds = []
    for row in extracted_data:
        p_hat = default_train_mean
        h = 1.0
        constant_preds.append((row["p"], p_hat, row["h_target"], h, row["student_id"]))
    baseline_reports["constant_mean"] = evaluate_single_predictor(constant_preds, "constant_mean", n_bootstraps)

    # Baseline 3: Historical Accuracy (n_right / (n_right + n_wrong), or 0.5 if new)
    hist_preds = []
    for row in extracted_data:
        c = row["counts"]
        total = c.n_right + c.n_wrong
        p_hat = (float(c.n_right) / float(total)) if total > 0 else 0.5
        h = 1.0
        hist_preds.append((row["p"], p_hat, row["h_target"], h, row["student_id"]))
    baseline_reports["historical_accuracy"] = evaluate_single_predictor(hist_preds, "historical_accuracy", n_bootstraps)

    from datetime import datetime, timezone
    return ComparisonReport(
        n_examples=len(examples),
        models=model_reports,
        baselines=baseline_reports,
        timestamp_utc=datetime.now(timezone.utc).isoformat()
    )
