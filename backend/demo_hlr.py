"""
backend/demo_hlr.py
Self-checking demonstration of the FocusFlow Half-Life Regression (HLR) engine.

Run from the backend folder:   python demo_hlr.py

Every step prints what the engine computed AND checks it against an independent
reference calculation written below from the plain formulas. At the end a
scoreboard shows PASS/FAIL for each check. The script exits with code 1 if any
check fails, so it can also be used in CI.

Change the values in the SETTINGS block to experiment. Nothing else needs editing.
"""
import math
import sys

from hlr.features import (
    ConceptCounts, RAW_SPEC, SQRT_SPEC, SQRT_DIFFICULTY_SPEC, extract_features,
)
from hlr.predictor import predict_half_life, predict_recall, predict_next_review_days
from hlr.updater import apply_outcome, HLR_V0_FIXED
from hlr.trainer import train_hlr, TrainerConfig
from ml.simulator import simulate_learners

# =============================================================================
# SETTINGS  (change these to experiment)
# =============================================================================

# --- Steps 1-2: prediction for one concept -----------------------------------
SPEC_NAME = "raw"              # "raw" -> [1, n_right, n_wrong]; "sqrt" -> [1, sqrt(n_right), sqrt(n_wrong)]
THETA = [0.0, 1.0, -1.0]       # weights [bias, right, wrong]. MUST match SPEC_NAME (see warning in Step 1)
N_RIGHT = 3                    # past correct answers on this concept
N_WRONG = 1                    # past wrong answers on this concept
THRESHOLD = 0.70               # recall level at which a review is scheduled
CURVE_MULTIPLES = [0, 0.5, 1, 2, 3, 5]   # elapsed time shown, as multiples of the half-life

# --- Step 3: state update after practice ------------------------------------
STEP3_START = (2, 2)           # (n_right, n_wrong) before practice; uses the launch model hlr_v0_fixed

# --- Step 4: difficulty feature (Module 14) ----------------------------------
DIFF_THETA = [0.10, 0.90, -0.90, -0.45]  # [bias, right, wrong, difficulty]; negative = Hard decays faster
DIFF_COUNTS = (2, 1)           # (n_right, n_wrong)

# --- Step 5: live training on synthetic learners ----------------------------
RUN_TRAINING = True
TRUE_THETA = [0.20, 0.85, -0.85]   # secret true weights used to create fake students
INIT_THETA = [0.0, 0.5, -0.5]       # where training starts (deliberately uncalibrated)
N_STUDENTS = 300
N_CONCEPTS = 4
N_SESSIONS = 6
QUESTIONS_PER_SESSION = 2          # independent right/wrong outcomes prevent feature collinearity
SEED = 42                          # same seed -> identical data every run
MAX_ITER = 150                     # optimisation steps allowed
LEARNING_RATE = 0.25               # size of each weight adjustment
ALPHA = 0.005                      # weight of the half-life error term in the loss
LAMBDA = 0.0001                    # strength of the penalty pulling weights toward zero
TOLERANCE = 0.15                   # learned weight must be within this of the true weight
CHECK_REPRODUCIBLE = True          # train twice with the same seed and compare

# =============================================================================
# Independent reference math (plain formulas, no library code)
# =============================================================================
H_MIN, H_MAX = 15 / 1440, 270.0
P_MIN, P_MAX = 0.0001, 0.9999
DIFFICULTY_SCORE = {"Easy": -1.0, "Medium": 0.0, "Hard": 1.0}


def ref_half_life(theta, x):
    return min(max(2.0 ** sum(t * v for t, v in zip(theta, x)), H_MIN), H_MAX)


def ref_recall(h, delta):
    return min(max(2.0 ** (-delta / h), P_MIN), P_MAX)


def ref_review_days(h, threshold):
    return -h * math.log2(threshold)


# =============================================================================
# Small helpers
# =============================================================================
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    tag = "PASS" if ok else "FAIL"
    print(f"    [{tag}] {name}" + (f"   ({detail})" if detail else ""))


def close(a, b, tol=1e-9):
    return abs(a - b) <= tol


def header(title):
    print("\n" + "=" * 72)
    print(f"  {title.upper()}")
    print("=" * 72)


# =============================================================================
# Steps
# =============================================================================
def step1_and_2():
    header("Step 1: Half-life, recall and review time for one concept")
    spec = RAW_SPEC if SPEC_NAME == "raw" else SQRT_SPEC
    counts = ConceptCounts(n_right=N_RIGHT, n_wrong=N_WRONG)
    x = extract_features(counts, spec)
    dot = sum(t * v for t, v in zip(THETA, x))
    h = predict_half_life(THETA, x)
    review = predict_next_review_days(h, threshold=THRESHOLD)

    print(f"  Spec: {SPEC_NAME}   counts: {N_RIGHT} right, {N_WRONG} wrong")
    print(f"  Features x = {[round(v, 4) for v in x]}")
    print(f"  Weights theta = {THETA}")
    print(f"  theta . x = {dot:.4f}  ->  half-life h = 2^{dot:.4f} = {h:.4f} days")
    print(f"  Review when recall hits {THRESHOLD:.0%}: after {review:.4f} days\n")

    if SPEC_NAME == "sqrt" and THETA == [0.0, 1.0, -1.0]:
        print("  WARNING: theta [0, 1, -1] was designed for RAW counts. Using it with sqrt")
        print("           features gives a different (shorter) half-life. Spec and weights")
        print("           must always be paired.\n")

    check("half-life matches reference formula", close(h, ref_half_life(THETA, x)), f"{h:.6f} days")
    check("recall at delta = h is exactly 0.5", close(predict_recall(h, h), 0.5))
    check("review time matches -h*log2(threshold)", close(review, ref_review_days(h, THRESHOLD)),
          f"{review:.6f} days")

    print("\n  Threshold sweep (same half-life, different review points):")
    prev = None
    ok_order = True
    for thr in (0.5, 0.7, 0.9):
        r = predict_next_review_days(h, threshold=thr)
        print(f"    threshold {thr:.2f} -> review after {r:8.4f} days ({r / h:.3f} x h)")
        if thr == 0.5:
            check("threshold 0.5 gives review time equal to the half-life", close(r, h))
        if prev is not None and not r < prev:
            ok_order = False
        prev = r
    check("higher threshold means earlier review", ok_order)

    header("Step 2: Forgetting curve")
    print(f"  Decay for h = {h:.3f} days:\n")
    print(f"  {'Elapsed (days)':>15} | {'Recall p':>9} | {'Retention':>9}")
    print("  " + "-" * 40)
    ps = []
    for m in CURVE_MULTIPLES:
        d = m * h
        p = predict_recall(h, d)
        ps.append(p)
        print(f"  {d:>15.3f} | {p:>9.4f} | {p * 100:>8.1f}%")
    print()
    check("recall never increases as time passes", all(a >= b for a, b in zip(ps, ps[1:])))
    check("recall at 0 days is capped at 0.9999 (never 1.0)", close(predict_recall(h, 0.0), P_MAX))
    check("recall at 2h is 0.25", close(predict_recall(h, 2 * h), 0.25))
    check("curve values match reference", all(
        close(predict_recall(h, m * h), ref_recall(h, m * h)) for m in CURVE_MULTIPLES))


def step3():
    header("Step 3: State update after practice (launch model hlr_v0_fixed)")
    theta = HLR_V0_FIXED.theta
    r0, w0 = STEP3_START
    base = ConceptCounts(n_right=r0, n_wrong=w0)
    base_h = predict_half_life(theta, extract_features(base, RAW_SPEC))
    print(f"  Start: {r0} right, {w0} wrong -> h = {base_h:.3f} days (theta = {list(theta)})")

    right = apply_outcome(base, n_right_new=1, n_wrong_new=0)
    right_h = predict_half_life(theta, extract_features(right, RAW_SPEC))
    wrong = apply_outcome(base, n_right_new=0, n_wrong_new=1)
    wrong_h = predict_half_life(theta, extract_features(wrong, RAW_SPEC))

    print(f"\n  [A] One more RIGHT answer: {right.n_right} right, {right.n_wrong} wrong")
    print(f"      h = {right_h:.3f} days ({(right_h / base_h - 1) * 100:+.0f}%)")
    print(f"  [B] One more WRONG answer: {wrong.n_right} right, {wrong.n_wrong} wrong")
    print(f"      h = {wrong_h:.3f} days ({(wrong_h / base_h - 1) * 100:+.0f}%)\n")

    check("right answer lengthens the half-life", right_h > base_h)
    check("wrong answer shortens the half-life", wrong_h < base_h)
    check("counts updated correctly (right)", (right.n_right, right.n_wrong) == (r0 + 1, w0))
    check("counts updated correctly (wrong)", (wrong.n_right, wrong.n_wrong) == (r0, w0 + 1))
    check("original counts not mutated", (base.n_right, base.n_wrong) == (r0, w0))
    if list(theta) == [0.0, 1.0, -1.0]:
        check("launch model: right answer doubles h", close(right_h, 2 * base_h))
        check("launch model: wrong answer halves h", close(wrong_h, 0.5 * base_h))

    print("\n  Clamping (extreme histories stay inside the allowed range):")
    hi = predict_half_life(theta, extract_features(ConceptCounts(n_right=20, n_wrong=0), RAW_SPEC))
    lo = predict_half_life(theta, extract_features(ConceptCounts(n_right=0, n_wrong=20), RAW_SPEC))
    print(f"    20 right, 0 wrong -> h = {hi:.4f} days (upper bound {H_MAX})")
    print(f"    0 right, 20 wrong -> h = {lo:.6f} days (lower bound {H_MIN:.6f} = 15 minutes)")
    check("upper bound holds", close(hi, H_MAX))
    check("lower bound holds", close(lo, H_MIN))


def step4():
    header("Step 4: Concept difficulty feature (Module 14)")
    r, w = DIFF_COUNTS
    print(f"  Weights [bias, right, wrong, difficulty] = {DIFF_THETA}")
    print(f"  Counts: {r} right, {w} wrong (sqrt features)\n")
    print(f"  {'Difficulty':<10} {'score':>6} | {'half-life':>10} | {'review in':>10}")
    print("  " + "-" * 46)
    hs = {}
    all_match = True
    for name in ("Easy", "Medium", "Hard"):
        x = extract_features(ConceptCounts(n_right=r, n_wrong=w), SQRT_DIFFICULTY_SPEC, {"difficulty": name})
        h = predict_half_life(DIFF_THETA, x)
        hs[name] = h
        ref_x = [1.0, math.sqrt(r), math.sqrt(w), DIFFICULTY_SCORE[name]]
        if not close(h, ref_half_life(DIFF_THETA, ref_x)):
            all_match = False
        rev = predict_next_review_days(h, threshold=THRESHOLD)
        print(f"  {name:<10} {DIFFICULTY_SCORE[name]:>6.1f} | {h:>8.3f} d | {rev:>8.3f} d")
    print()
    check("difficulty half-lives match reference", all_match)
    d = DIFF_THETA[3]
    if d < 0:
        check("negative weight: Easy > Medium > Hard", hs["Easy"] > hs["Medium"] > hs["Hard"])
    elif d > 0:
        check("positive weight: Hard > Medium > Easy", hs["Hard"] > hs["Medium"] > hs["Easy"])
    else:
        check("zero weight: difficulty has no effect", close(hs["Easy"], hs["Hard"]))
    x_unknown = extract_features(ConceptCounts(n_right=r, n_wrong=w), SQRT_DIFFICULTY_SPEC,
                                 {"difficulty": "Unrecognised"})
    check("unknown difficulty is treated as Medium (score 0)",
          close(predict_half_life(DIFF_THETA, x_unknown), hs["Medium"]))


def train_once():
    records = simulate_learners(
        theta_true=TRUE_THETA, feature_spec=RAW_SPEC,
        n_students=N_STUDENTS, n_concepts=N_CONCEPTS, n_sessions=N_SESSIONS,
        questions_per_session=QUESTIONS_PER_SESSION,
        exact_mode=True, seed=SEED,
    )
    cfg = TrainerConfig(max_iterations=MAX_ITER, learning_rate=LEARNING_RATE,
                        alpha=ALPHA, lambda_=LAMBDA)
    artifact, report = train_hlr(records, list(INIT_THETA), RAW_SPEC, cfg)
    return records, artifact, report


def step5():
    header("Step 5: Live training (AdaGrad, Settles & Meeder loss)")
    print(f"  True weights:   {TRUE_THETA}")
    print(f"  Start weights:  {INIT_THETA}")
    print(f"  Data: {N_STUDENTS} students x {N_CONCEPTS} concepts x {N_SESSIONS} sessions, seed {SEED}")
    print(f"  Optimiser: {MAX_ITER} iterations, learning rate {LEARNING_RATE}, "
          f"alpha {ALPHA}, lambda {LAMBDA}\n")
    try:
        records, artifact, report = train_once()
    except Exception as exc:  # report the problem instead of crashing the whole demo
        check("training run completes without error", False, f"{type(exc).__name__}: {exc}")
        return

    theta = list(artifact.theta)
    first, last = report.losses[0], report.losses[-1]
    print(f"  Records generated: {len(records)}")
    print(f"  Loss: {first:.6f} -> {last:.6f}  ({(1 - last / first) * 100:.1f}% lower)"
          if first > 0 else f"  Loss: {first:.6f} -> {last:.6f}")
    print(f"  Converged: {report.converged}   stopped at iteration {report.stopped_iteration}\n")
    print(f"  {'weight':<8} {'true':>8} {'learned':>9} {'error':>8}")
    print("  " + "-" * 36)
    names = ["bias", "right", "wrong"]
    errors = []
    for n, t, l in zip(names, TRUE_THETA, theta):
        errors.append(abs(l - t))
        print(f"  {n:<8} {t:>8.3f} {l:>9.3f} {abs(l - t):>8.3f}")
    print()
    check("training produced records", len(records) > 0)
    check("all learned weights are finite", all(math.isfinite(v) for v in theta))
    check("training loss decreased", last < first)
    check(f"every weight within {TOLERANCE} of the truth", max(errors) <= TOLERANCE,
          f"largest error {max(errors):.3f}")
    if CHECK_REPRODUCIBLE:
        _, artifact2, _ = train_once()
        check("same seed gives identical weights",
              all(close(a, b, 1e-12) for a, b in zip(theta, artifact2.theta)))
    if max(errors) > TOLERANCE:
        print("  Hint: if the weight check failed, try a larger MAX_ITER before suspecting a bug.")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    header("FocusFlow HLR: self-checking demonstration")
    step1_and_2()
    step3()
    step4()
    if RUN_TRAINING:
        step5()

    header("Scoreboard")
    passed = sum(1 for _, ok in RESULTS if ok)
    total = len(RESULTS)
    for name, ok in RESULTS:
        if not ok:
            print(f"  FAILED: {name}")
    print(f"\n  {passed} of {total} checks passed.")
    if passed == total:
        print("  RESULT: all checks passed. The equations and the trainer behave as expected")
        print("          on synthetic data. (This does not prove accuracy on real students.)\n")
        sys.exit(0)
    print("  RESULT: at least one check FAILED. Read the FAIL lines above before trusting the engine.\n")
    sys.exit(1)


if __name__ == "__main__":
    main()