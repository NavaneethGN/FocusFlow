"""
backend/hlr/trainer.py
AdaGrad Trainer for Half-Life Regression using Settles & Meeder (2016) full loss.
Pure Python + standard math / standard library. No active model or DB mutation.

Loss on example i:
  z = theta . x
  h = 2 ** z
  p_hat = 2 ** (-delta / h)
  h_target = clip(-delta / log2(clip(p, p_min, p_max)), h_min, h_max)
  loss = (p - p_hat)^2 + alpha * (h - h_target)^2 + lambda * ||theta||^2
"""
from dataclasses import dataclass, field
import math
import random
from typing import Sequence, List, Tuple, Dict, Any, Optional

from .config import HLRConfig
from .features import FeatureSpec, RAW_SPEC
from .predictor import HLRValidationError, predict_half_life, predict_recall
from .updater import ModelArtifact

@dataclass(frozen=True)
class TrainerConfig:
    """Hyperparameters for HLR model training and AdaGrad optimization."""
    alpha: float = 0.01                 # Half-life error weight
    lambda_: float = 0.1                # L2 penalty weight
    learning_rate: float = 0.05
    epsilon: float = 1e-8               # AdaGrad denominator smoother
    max_iterations: int = 500
    gradient_clip: float = 10.0
    exclude_bias_from_l2: bool = True
    use_sample_weights: bool = False
    early_stopping_patience: int = 25
    seed: int = 42
    h_min: float = 15.0 / 1440.0
    h_max: float = 270.0
    p_min: float = 0.0001
    p_max: float = 0.9999

@dataclass
class TrainingReport:
    """Detailed telemetry and audit report for a model training execution."""
    losses: List[float]
    val_losses: List[float]
    final_gradient_norm: float
    converged: bool
    stopped_iteration: int
    bounds_fraction: float
    config: Dict[str, Any]
    seed: int

LN2 = math.log(2.0)
LN2_SQ = LN2 * LN2

def _extract_example_fields(example: Any) -> Tuple[float, float, List[float], int]:
    """Helper to extract (p_observed, delta_days, x_before, n_answers)."""
    if isinstance(example, dict):
        p = example["p_observed"]
        delta = example["delta_days"]
        x = example["x_before"]
        n = example.get("n_answers", 1)
    else:
        p = getattr(example, "p_observed")
        delta = getattr(example, "delta_days")
        x = getattr(example, "x_before")
        n = getattr(example, "n_answers", 1)

    if not isinstance(p, (int, float)) or math.isnan(p) or math.isinf(p):
        raise HLRValidationError(f"Invalid non-finite label p: {p!r}")
    if not isinstance(delta, (int, float)) or math.isnan(delta) or math.isinf(delta) or delta <= 0:
        raise HLRValidationError(f"Invalid non-positive delta_days: {delta!r}")
    for idx, v in enumerate(x):
        if not isinstance(v, (int, float)) or math.isnan(v) or math.isinf(v):
            raise HLRValidationError(f"Invalid non-finite feature x[{idx}]: {v!r}")

    return float(p), float(delta), [float(v) for v in x], int(n)

def compute_loss_and_gradient(
    theta: Sequence[float],
    examples: Sequence[Any],
    config: TrainerConfig
) -> Tuple[float, List[float]]:
    """Computes total mean loss and analytic gradient vector over examples.
    
    Treats h_target as constant with respect to theta.
    Uses unclipped h in the gradient per Settles & Meeder (2016).
    """
    n_params = len(theta)
    if len(examples) == 0:
        raise HLRValidationError("Cannot compute loss/gradient on empty examples")

    total_loss = 0.0
    grad = [0.0] * n_params
    total_weight = 0.0

    for ex in examples:
        p, delta, x, n_answers = _extract_example_fields(ex)
        weight = float(n_answers) if config.use_sample_weights else 1.0
        total_weight += weight

        # Dot product
        z = sum(t * v for t, v in zip(theta, x))
        # h = 2 ** z
        try:
            h = 2.0 ** z
        except OverflowError:
            h = config.h_max

        # Guard against zero or extreme half life
        h = max(1e-12, h)

        # p_hat = 2 ** (-delta / h)
        p_hat = 2.0 ** (-delta / h)
        p_hat_clamped = min(max(p_hat, config.p_min), config.p_max)

        # h_target = clip(-delta / log2(clip(p, p_min, p_max)), h_min, h_max)
        p_clipped = min(max(p, config.p_min), config.p_max)
        log2_p = math.log2(p_clipped)
        # log2_p is strictly negative since p_clipped <= p_max < 1
        raw_h_target = -delta / log2_p
        h_target = min(max(raw_h_target, config.h_min), config.h_max)

        # Example loss: Settles & Meeder (2016) uses unclamped p_hat in loss
        p_err = (p - p_hat) ** 2
        h_err = config.alpha * ((h - h_target) ** 2)
        ex_loss = p_err + h_err
        total_loss += weight * ex_loss

        # Analytic gradient components with respect to z
        # d(p_err)/dz = 2 * (p_hat - p) * p_hat * (ln 2)^2 * (delta / h)
        dp_dz = 2.0 * (p_hat - p) * p_hat * LN2_SQ * (delta / h)
        # d(h_err)/dz = 2 * alpha * (h - h_target) * h * ln 2
        dh_dz = 2.0 * config.alpha * (h - h_target) * h * LN2
        dz_total = dp_dz + dh_dz

        for j in range(n_params):
            grad[j] += weight * dz_total * x[j]

    # Normalize by total weight
    mean_loss = total_loss / total_weight
    for j in range(n_params):
        grad[j] /= total_weight

    # L2 regularization
    l2_penalty = 0.0
    for j in range(n_params):
        is_bias = (j == 0 and config.exclude_bias_from_l2)
        if not is_bias:
            l2_penalty += config.lambda_ * (theta[j] ** 2)
            grad[j] += 2.0 * config.lambda_ * theta[j]

    mean_loss += l2_penalty

    if math.isnan(mean_loss) or math.isinf(mean_loss):
        raise HLRValidationError(f"Non-finite loss computed: {mean_loss}")

    return mean_loss, grad

def gradient_check(
    theta: Sequence[float],
    examples: Sequence[Any],
    config: TrainerConfig,
    eps: float = 1e-6
) -> float:
    """Verifies analytic gradient against central finite differences.
    Returns maximum relative error across all parameters.
    """
    _, analytic_grad = compute_loss_and_gradient(theta, examples, config)
    max_rel_error = 0.0

    theta_list = list(theta)
    for j in range(len(theta_list)):
        theta_plus = list(theta_list)
        theta_minus = list(theta_list)
        theta_plus[j] += eps
        theta_minus[j] -= eps

        loss_plus, _ = compute_loss_and_gradient(theta_plus, examples, config)
        loss_minus, _ = compute_loss_and_gradient(theta_minus, examples, config)

        numeric_grad = (loss_plus - loss_minus) / (2.0 * eps)
        ana = analytic_grad[j]

        denom = max(abs(ana) + abs(numeric_grad), 1e-8)
        rel_error = abs(ana - numeric_grad) / denom
        if rel_error > max_rel_error:
            max_rel_error = rel_error

    return max_rel_error

def train_hlr(
    examples: Sequence[Any],
    initial_theta: Sequence[float],
    feature_spec: FeatureSpec,
    config: Optional[TrainerConfig] = None,
    val_examples: Optional[Sequence[Any]] = None
) -> Tuple[ModelArtifact, TrainingReport]:
    """Trains HLR model using AdaGrad on the given dataset.
    
    Early stopping evaluates on val_examples (or subset of examples if None).
    Never mutates active model or database state.
    """
    cfg = config or TrainerConfig()
    theta = [float(t) for t in initial_theta]
    n_params = len(theta)

    if len(theta) != len(feature_spec.feature_names):
        raise HLRValidationError(
            f"initial_theta length {len(theta)} does not match feature spec '{feature_spec.name}' count {len(feature_spec.feature_names)}"
        )

    # Initialize AdaGrad historical squared gradient accumulator
    G = [0.0] * n_params

    losses: List[float] = []
    val_losses: List[float] = []

    best_val_loss = float("inf")
    best_theta = list(theta)
    patience_counter = 0

    eval_val = val_examples if val_examples and len(val_examples) > 0 else examples

    for iteration in range(cfg.max_iterations):
        loss, grad = compute_loss_and_gradient(theta, examples, cfg)
        losses.append(loss)

        # Validation loss for early stopping
        val_loss, _ = compute_loss_and_gradient(theta, eval_val, cfg)
        val_losses.append(val_loss)

        if val_loss < best_val_loss - 1e-6:
            best_val_loss = val_loss
            best_theta = list(theta)
            patience_counter = 0
        else:
            patience_counter += 1

        if patience_counter >= cfg.early_stopping_patience:
            break

        # Compute gradient norm and clip if necessary
        grad_norm = math.sqrt(sum(g ** 2 for g in grad))
        if grad_norm > cfg.gradient_clip:
            scale = cfg.gradient_clip / grad_norm
            grad = [g * scale for g in grad]

        # AdaGrad update step
        for j in range(n_params):
            G[j] += grad[j] ** 2
            step = (cfg.learning_rate / math.sqrt(G[j] + cfg.epsilon)) * grad[j]
            theta[j] -= step

    final_theta = best_theta
    final_loss, final_grad = compute_loss_and_gradient(final_theta, examples, cfg)
    final_grad_norm = math.sqrt(sum(g ** 2 for g in final_grad))

    # Calculate fraction of predictions at bounds
    at_bounds_count = 0
    for ex in examples:
        _, _, x, _ = _extract_example_fields(ex)
        h = predict_half_life(final_theta, x)
        if abs(h - cfg.h_min) < 1e-6 or abs(h - cfg.h_max) < 1e-6:
            at_bounds_count += 1
    bounds_fraction = at_bounds_count / float(len(examples))

    artifact = ModelArtifact(
        name=f"hlr_trained_{feature_spec.name}",
        theta=final_theta,
        feature_spec=feature_spec,
        config=HLRConfig(
            h_min_days=cfg.h_min,
            h_max_days=cfg.h_max,
            p_min=cfg.p_min,
            p_max=cfg.p_max
        )
    )

    report = TrainingReport(
        losses=losses,
        val_losses=val_losses,
        final_gradient_norm=final_grad_norm,
        converged=(patience_counter >= cfg.early_stopping_patience or iteration == cfg.max_iterations - 1),
        stopped_iteration=len(losses),
        bounds_fraction=bounds_fraction,
        config={
            "alpha": cfg.alpha,
            "lambda_": cfg.lambda_,
            "learning_rate": cfg.learning_rate,
            "gradient_clip": cfg.gradient_clip,
            "exclude_bias_from_l2": cfg.exclude_bias_from_l2
        },
        seed=cfg.seed
    )

    return artifact, report
