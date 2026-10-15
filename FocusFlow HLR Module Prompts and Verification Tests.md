# FocusFlow HLR: Module Prompts and Verification Tests

*Build prompts for a coding assistant, one per module, each with tests that prove the module works. Revised after the repo review: it upgrades the partial HLR code that already exists.*

## How to use this document

Work top to bottom. Every module has three parts: a **Prompt** to paste into your coding assistant, **Verification tests** that must pass, and a **Done when** line. Do not start the next module until the current one is green.

Paste the shared context below at the top of every prompt. It keeps the assistant consistent across sessions.

## Where the repo stands today

The repo already has correct HLR prediction math but a fixed theta and no learning, so these prompts extract and harden what exists before adding training.

| Finding in the review | What changes in the prompts |
| --- | --- |
| Recall, half-life and review-interval math is correct | Extract it, do not rewrite it; prove parity against frozen copies of the old functions |
| `LAUNCH_THETA = [0, 1, -1]` is hard-coded and acts like a Leitner box | It becomes the model `hlr_v0_fixed`, the baseline every trained model must beat |
| Features are only `[1, n_right, n_wrong]` | Keep that order (drop `times_seen`, it is redundant); add difficulty later in Module 14 |
| `p_session` is computed, then discarded | Module 6 saves it as a training record |
| No loss function, trainer or training data | Module 8 implements the paper's full loss, including the half-life and L2 terms |
| Data lives in in-memory lists (`db_attempts`, `db_practice_history`) | Module 4 adds a repository layer: in-memory first, PostgreSQL second, one shared contract test suite |
| `/api/models` returns invented metrics and an untrained second model | Module 0 removes the fake numbers; Module 10 makes the endpoint registry-backed |
| The frontend has its own JS copy of the math | Shared test vectors keep Python and JS in parity |
| Everything sits in `backend/main.py` | New code goes in packages under `backend/`; `main.py` shrinks step by step |

### Shared context (paste first, every time)

```text
Project: FocusFlow, an AI study planner. Backend: FastAPI in backend/main.py (one file today, data in in-memory Python lists such as db_attempts and db_practice_history). Frontend: React + Vite in frontend/, with a JS copy of the HLR math in frontend/src/main.jsx.
We are UPGRADING a partial HLR implementation, not starting fresh. Current behaviour to preserve:
  LAUNCH_THETA = [0.0, 1.0, -1.0]; features x = [1, n_right, n_wrong]
  half_life(theta, x), recall_prob(h, delta_days), next_review_days(h, threshold=0.70)
  bounds H_MIN=15/1440 days, H_MAX=270, P_MIN=0.0001, P_MAX=0.9999
HLR equations:
  h = 2 ** (theta . x)    p_hat = 2 ** (-delta / h)    review interval = -h * log2(threshold)
Feature specs: raw_counts = [1, n_right, n_wrong]; sqrt_counts = [1, sqrt(n_right), sqrt(n_wrong)].
Target layout (new code goes here; main.py shrinks as logic moves out):
  backend/hlr/          config, features, predictor, updater, review_policy, trainer, evaluation
  backend/ml/           simulator, dataset_builder, model_registry, promotion
  backend/learning/     session_aggregator, training_record_builder
  backend/repositories/ base, memory, postgres
  backend/scheduler/  backend/jobs/  backend/tests/
Rules:
1. Refactor in small steps. The app must keep running and existing API response shapes must not change unless the prompt says so. Run the characterization tests after every step.
2. theta and feature_spec are one indivisible, versioned artifact.
3. backend/hlr is pure Python: no DB, HTTP, FastAPI or Gemini imports.
4. Never trust client-supplied counts, features, correctness or elapsed time.
5. Mark every choice that depends on the HLR paper (Settles & Meeder, 2016) with ASSUMPTION in a docstring so I can verify it.
6. Never invent metrics. A number may appear in an API response only if code computed it from data.
7. Write the tests in the same change as the code. Do not move on until they pass.
Answer with: files changed, how to run the tests, and any assumptions.
```

---

## Module 0: Safety net and cleanup of misleading output

Do this before touching any logic. It freezes today's behaviour so every later step can prove it changed nothing by accident.

**Prompt**

```text
[Shared context]
Before changing any logic, protect current behaviour.
1. Create backend/tests/legacy_reference.py with verbatim copies of the current half_life, recall_prob, next_review_days and LAUNCH_THETA from main.py. Never edit it again; it is the frozen reference.
2. Write characterization tests (tests/test_characterization.py) using FastAPI TestClient. Run one scripted scenario: create concepts, answer questions, complete a session, then fetch the dashboard, plan and curve responses. Snapshot the JSON to tests/snapshots/. Freeze time or add an injectable clock so snapshots are stable.
3. Create tests/hlr_test_vectors.json with at least 40 cases [theta, x, delta_days, threshold, half_life, recall, next_review_days] generated from legacy_reference.py. Add a pytest that checks the Python functions against it and a Vitest test (frontend/src/hlr.test.js) that checks calcHalfLife, calcRecallProb and calcNextReviewDays against the same file.
4. Fix the misleading /api/models response. Remove the invented numbers ('Half-life Log-Loss MAE: 0.124', 'AdaGrad Offline MAE: 0.089, AUC: 0.812'). Return metrics as null with status 'provisional_fixed_weights' for the active model, and mark the second model (hlr-trained-sqrt-v2) as 'placeholder_untrained' or remove it. Change nothing else.
5. Add a guard test that fails if any model metric in an API response is a number not produced by an evaluation run (for now: all must be null).
```

**Verification tests**

| Test | Expected |
| --- | --- |
| Characterization snapshots | pass on the untouched code; editing a formula breaks them |
| Vector file | 40 or more cases, including delta=0, delta=h, theta·x = ±30 (clamping) and negative delta |
| Python vs vectors | every case matches within 1e-12 |
| JS vs vectors | every case matches within 1e-12 under Vitest |
| Negative delta | recorded as current behaviour: legacy clamps it to 0 |
| `/api/models` | no numeric metrics; no `loss_metric` or `auc` values |
| Source search | the strings 0.124, 0.089 and 0.812 appear nowhere in backend or frontend source |
| App boot | uvicorn starts and the existing frontend loads without console errors |

**Done when:** all rows pass on the repo exactly as it is today, before any refactor.

---

## Module 1: Extract and harden the predictor (pure math)

**Prompt**

```text
[Shared context]
Create backend/hlr/config.py and backend/hlr/predictor.py by EXTRACTING the math that is now inside main.py.
config.py: frozen dataclass HLRConfig(h_min_days=15/1440, h_max_days=270.0, p_min=0.0001, p_max=0.9999, review_threshold=0.70, default_model='hlr_v0_fixed').
predictor.py: predict_half_life(theta, x, config), predict_recall(half_life_days, delta_days, config), predict_next_review_days(half_life_days, threshold, config), raw_log2_half_life(theta, x) (unclipped, for monitoring).
Validate equal lengths and finiteness; raise HLRValidationError with a clear message; reject negative delta, non-positive half-life and thresholds outside (0, 1). Standard library only.
Backward compatibility: in main.py keep the old names and signatures as thin wrappers over the new functions. The legacy recall_prob silently clamps negative delta to 0: keep that in the wrapper only and document it; the core function must raise.
Do not touch the frontend in this step.
Write tests/test_predictor.py, including parity tests against tests/legacy_reference.py and tests/hlr_test_vectors.json.
```

**Verification tests**

| Test | Input | Expected |
| --- | --- | --- |
| Delta equals half-life | h=4, delta=4 | recall 0.5 (within 1e-9) |
| Double half-life | h=4, delta=8 | recall 0.25 |
| Zero elapsed | h=4, delta=0 | 0.9999 (capped, not 1.0) |
| Monotonic in delta | delta 0 to 100 | recall never increases |
| Monotonic in half-life | h 0.1 to 200, fixed delta | recall never decreases |
| Review at 0.7 | h=4 | about 2.058 days (0.5146 × h) |
| Review at 0.5 | any h | interval equals h |
| Upper bound | theta·x = 30 | h = 270 exactly |
| Lower bound | theta·x = -30 | h = 15/1440 |
| Raw vs bounded | theta·x = 30 | raw\_log2\_half\_life = 30, bounded h = 270 |
| Bad input | NaN, inf, length mismatch, delta=-1, threshold 0 or 1 | HLRValidationError |
| Legacy parity | 10,000 random finite inputs | new equals tests/legacy\_reference.py within 1e-12 (non-negative delta) |
| Legacy wrapper | main.recall\_prob(4, -1) | equals the legacy result; the core function raises |
| Vector file | tests/hlr\_test\_vectors.json | every case passes |
| Characterization | Module 0 snapshots | unchanged |
| Property test (hypothesis) | random finite theta, x | h inside bounds; recall in \[0.0001, 0.9999\] |

**Done when:** every row passes, each wrapper in main.py is three lines or fewer, no HLR formula remains in main.py, and `backend/hlr` imports no web or database code.

---

## Module 2: Versioned feature extraction

**Prompt**

```text
[Shared context]
Create backend/hlr/features.py. The repo's feature vector is [1.0, n_right, n_wrong]: keep exactly that order and those names (concept records already use n_right and n_wrong). Do NOT add times_seen; it equals n_right + n_wrong.
FeatureSpec dataclass: name ('raw_counts' | 'sqrt_counts'), feature_names, feature_order_version, transform(counts).
ConceptCounts(n_right, n_wrong): non-negative, finite integers; reject bool, float and NaN.
extract_features(counts, spec) -> [1.0, f(n_right), f(n_wrong)] where f is identity for raw_counts and sqrt for sqrt_counts.
is_new(counts) -> n_right + n_wrong == 0. Never infer a recall value for a new concept in this module.
get_spec(name) raises on unknown names; spec_hash(spec) is stable across runs.
In main.py replace the inline x = [1.0, n_right, n_wrong] with extract_features(counts, RAW_SPEC). Behaviour must not change.
Write tests/test_features.py.
```

**Verification tests**

| Test | Input | Expected |
| --- | --- | --- |
| Raw example | n\_right=3, n\_wrong=1 | \[1, 3, 1\] |
| Sqrt example | n\_right=3, n\_wrong=1 | \[1, 1.7320508, 1\] |
| Another raw example | n\_right=5, n\_wrong=3 | \[1, 5, 3\] |
| New concept | 0 and 0 | \[1, 0, 0\] and is\_new is True |
| Determinism | same counts called 1000 times | identical vectors |
| Negative count | n\_right=-1 | validation error |
| Non-integer count | n\_wrong=2.5, NaN, True | validation error |
| Spec mismatch | theta of length 2 with a 3-feature spec | error at model load, not at predict |
| Spec hash | same spec twice, then a changed feature order | equal hash, then different hash |
| Characterization | Module 0 snapshots | unchanged |

**Done when:** both specs produce the vectors above, the inline vector in main.py is gone, and changing the feature order changes `spec_hash`.

---

## Module 3: Fixed model, updater and review policy

**Prompt**

```text
[Shared context]
Create backend/hlr/updater.py and backend/hlr/review_policy.py.
ModelArtifact(name, theta, feature_spec, config): validated at construction (len(theta) equals the feature count).
Define hlr_v0_fixed from the EXISTING LAUNCH_THETA = [0.0, 1.0, -1.0] with the raw_counts spec. Document it as PROVISIONAL and Leitner-equivalent (every right doubles the half-life, every wrong halves it); it is not the paper's trained model and it is the baseline every trained model must beat. Move LAUNCH_THETA into this definition and keep an alias in main.py.
updater.apply_outcome(counts, n_right_new, n_wrong_new) -> new ConceptCounts (pure function, no mutation).
updater.compute_state(counts, model, last_practiced_at, now) -> ConceptStateResult(half_life_days, recall_now, next_review_at, is_new). For a never-practiced concept return recall_now=None and next_review_at=now.
review_policy.next_review_at(last_practiced_at, half_life_days, threshold) -> timezone-aware UTC datetime.
In main.py replace the post-session update (new_x = [...]; new_h = half_life(LAUNCH_THETA, new_x)) with compute_state. Existing outputs must not change.
Write tests/test_updater.py and tests/test_review_policy.py.
```

**Verification tests**

| Test | Input | Expected |
| --- | --- | --- |
| New concept default | 0 right, 0 wrong | h = 1 day |
| Review example | 5 right, 3 wrong | h = 4 days (2^2) |
| Wrong shortens | 0 right, 2 wrong | h = 0.25 days |
| Legacy parity grid | n\_right and n\_wrong each 0 to 30 | compute\_state half-life equals the legacy new\_h (clamped) for all 961 pairs |
| Monotonic learning | add one right answer to any state | h doubles unless clamped |
| Immutability | apply\_outcome | returns a new object; the original is unchanged |
| Next review time | last = T, h = 4, threshold 0.7 | T + 2.058 days |
| Recall now | h = 4, 4 days elapsed | 0.5 |
| Overdue concept | now past next\_review\_at | recall\_now < 0.7 |
| Naive datetime | timezone-naive input | error |
| Model construction | theta of length 2 with the raw spec | error |
| Characterization | Module 0 snapshots | unchanged |

**Done when:** the half-life update in main.py is a single call to compute\_state, the parity grid passes, and a scripted example (5 right, 3 wrong, then 5 idle days) prints the half-life, recall and next review date you expect by hand.

---

## Module 4: Persistence behind a repository layer

**Prompt**

```text
[Shared context]
Today data lives in in-memory Python lists (db_attempts, db_practice_history and similar in main.py). ASSUMPTION: no real database exists yet. If one does, adapt this prompt and tell me.
Step 1: define repository interfaces in backend/repositories/base.py: AttemptRepo, SessionRepo, ConceptStateRepo, PracticeHistoryRepo, TrainingRecordRepo, ModelRepo, each with a unit-of-work (transaction) context.
Step 2: write InMemory implementations that wrap the existing lists, and switch main.py to use them. Behaviour must not change.
Step 3: write PostgreSQL implementations (SQLAlchemy 2.0 + Alembic), chosen by env var REPO_BACKEND=memory|postgres. Tables:
  attempts: id, event_id UNIQUE, student_id, session_id, question_id, concept_id, correct bool, answered_at, selected_option, response_time_ms nullable, hint_used. Append-only (reject UPDATE and DELETE).
  sessions: id, student_id, started_at, completed_at nullable, status enum (open, processing, completed, cancelled), result_json nullable.
  concept_state: UNIQUE (student_id, concept_id); n_right, n_wrong, last_practiced_at, half_life_days, recall_prob_now, next_review_at, model_version, version int (optimistic lock), updated_at.
  practice_history: the data behind today's db_practice_history, unchanged in meaning.
  training_records: id, student_id, concept_id, session_id, p_observed, n_answers, delta_days, counts_before JSONB, x_before JSONB, feature_spec_name, label_definition_version, model_version, source_event_ids JSONB, created_at. UNIQUE (session_id, concept_id).
  model_versions: id, name, version, theta JSONB, feature_spec JSONB, training_config JSONB, dataset_snapshot_id, evaluation_metrics JSONB, validation_status enum, active bool, checksum, created_at. A partial unique index allows at most one active row.
  CHECK constraints: n_right >= 0, n_wrong >= 0, p_observed between 0 and 1, n_answers >= 1.
Write ONE contract test suite in tests/test_repositories.py that runs against both implementations (pytest parametrize). Use a real PostgreSQL test database (docker or testcontainers), not SQLite.
```

**Verification tests**

| Test | Expected |
| --- | --- |
| Contract suite | identical tests pass for the in-memory and PostgreSQL repositories |
| Backend switch | Module 0 snapshots pass with REPO\_BACKEND=memory and with REPO\_BACKEND=postgres |
| `alembic upgrade head`, `downgrade base`, `upgrade head` | succeeds with no errors |
| Two attempts with the same event\_id | duplicate error from both implementations |
| UPDATE or DELETE on attempts | rejected by both |
| Two concept\_state rows for one student and concept | error |
| Two training\_records for one session and concept | error |
| Two model\_versions with active = true | error (PostgreSQL index, memory guard) |
| p\_observed = 1.2, n\_answers = 0, n\_right = -1 | CHECK violation |
| Alembic autogenerate after the migration | empty diff |
| Process restart | PostgreSQL data survives; in-memory data does not (documented, not a bug) |

**Done when:** the app runs on either backend with identical snapshots, and every constraint above is enforced by the database itself, not only by Python.

---

## Module 5: Answer ingestion (idempotent, server-scored)

**Prompt**

```text
[Shared context]
Harden the EXISTING answer-submission endpoint in main.py (the one that appends to db_attempts). Do not create a second endpoint.
Add to the request: event_id (client-generated UUID). Keep every field the frontend already sends so the frontend keeps working.
The server must: identify the student; verify the session belongs to them and is open; load the question; compute correctness from the stored answer, ignoring any client-supplied correct value; take concept_id from the question; store the attempt through AttemptRepo.
If the repo has no authentication yet, add a get_current_student dependency (for dev: read an X-Student-Id header) so tests are written against the real interface and real auth can replace it later.
A duplicate event_id returns 200 with the originally stored result and inserts nothing. Another student reusing an event_id must not see the first student's data.
Reject: answers to completed or cancelled sessions, unknown questions, questions that are not approved, answered_at more than 5 minutes in the future.
Keep the response JSON shape the frontend expects (snapshot it first); only add fields.
Write tests/test_answers_api.py.
```

**Verification tests**

| Test | Expected |
| --- | --- |
| Valid answer | 201 and one attempt row; correct matches the stored answer |
| Same event\_id sent 5 times | one row, identical responses |
| Client sends `correct: true` for a wrong choice | ignored; stored as false |
| Another student's session | 403 or 404, nothing written |
| Completed session | 409 |
| Draft or flagged question | 422 |
| Future timestamp | 422 |
| 20 concurrent requests, same event\_id | exactly one row |
| Missing student identity | 401 |
| Response shape | existing keys unchanged against the Module 0 snapshot |

**Done when:** the concurrent-duplicate test passes 50 runs in a row and the unchanged frontend still submits answers.

---

## Module 6: Session completion pipeline

**Prompt**

```text
[Shared context]
Find the existing session-completion endpoint in main.py. It computes p_session = correct / total, updates n_right and n_wrong, and sets the new half-life. Move that logic into backend/learning/session_aggregator.py and training_record_builder.py and call them from the endpoint. Keep the existing response and practice-history output unchanged; the training data is new behaviour on top.
Run in ONE repository transaction:
1. Lock the session. If it is already completed, return the stored result_json and change nothing.
2. Group scored attempts by concept.
3. Lock or version-check each concept_state row (create it when missing).
4. p = correct / scored answers. delta_days = completed_at minus last_practiced_at.
5. If the concept was practiced before, save a training_record: p_observed, n_answers, delta_days, counts_before, x_before (computed BEFORE incrementing counts), feature_spec_name, model_version, source_event_ids. This closes the current gap where p_session is computed and then discarded.
6. First practice: no training record (no delta), but initialise concept_state.
7. Increment n_right and n_wrong, load the active model, call compute_state, persist half-life, recall, next_review_at and model_version.
8. Mark the session completed and store result_json.
If any step fails, nothing is persisted.
ASSUMPTIONS to document: delta runs from the previous session's completion time to this session's; the label is the session fraction with n_answers stored (the paper's labels are single recalls or lag-bin proportions, so keep n_answers for weighting).
Write tests/test_session_complete.py.
```

**Verification tests**

| Test | Expected |
| --- | --- |
| Session recall example | BFS 3 of 4, DFS 1 of 2, Trees 0 of 3 give p = 0.75, 0.50, 0.00 |
| x\_before correctness | prior 3 right, 1 wrong; sqrt spec; session adds 2 right, 1 wrong: x\_before = \[1, 1.732, 1\]; state becomes 5 right, 2 wrong |
| No future leakage | x\_before never equals the post-update vector |
| Legacy parity | with hlr\_v0\_fixed active, every half-life equals what the old code produced for the same scenario |
| Fixes the discard | every previously practiced concept yields one training record holding p\_session |
| First practice | state created, zero training records |
| Second practice | exactly one training record with delta > 0 |
| Retry safety | calling complete twice changes nothing; the second response equals the first |
| Concurrent completes | 10 parallel calls give one update |
| Failure rollback | an injected exception after the training record: no record, no count change, session still open |
| Concept with no scored answers | skipped, no division by zero |
| Model tagging | state stores the active model name; the record stores the feature spec used |
| Replayed events | duplicate event\_ids do not inflate counts |
| Response shape | existing keys unchanged against Module 0 snapshots |

**Done when:** the rollback, concurrent-complete and legacy-parity tests pass, and p\_session is no longer discarded.

---

## Module 7: Synthetic learner simulator

**Prompt**

```text
[Shared context]
Create backend/ml/simulator.py (numpy, seedable). It generates synthetic training data with KNOWN weights so the trainer can be tested against ground truth.
simulate_learners(theta_true, feature_spec, n_students, n_concepts, n_sessions, questions_per_session, interval_distribution, label_mode, seed) returns training records in EXACTLY the schema the real pipeline writes (p_observed, n_answers, delta_days, counts_before, x_before, feature_spec_name).
label_mode: 'session_fraction' (Bernoulli draws per question, p = fraction correct) or 'binary' (one recall per record, n_answers = 1, closest to the paper). exact_mode=True returns p_true directly with no sampling noise.
Draw outcomes from p_true = 2 ** (-delta / h_true), with h_true from theta_true and the current counts. After each session update counts with updater.apply_outcome.
Import predictor, features and updater instead of copying their math.
Default truths for tests: theta_true = [0, 1, -1] with raw_counts (the current launch model) and theta_true = [0.15, 1.42, -1.18] with sqrt_counts (the numbers the fake 'trained' model in /api/models claimed).
Write tests/test_simulator.py.
```

**Verification tests**

| Test | Expected |
| --- | --- |
| Determinism | same seed gives identical output; a different seed differs |
| Schema parity | records have the same fields and types as real training\_records |
| Label bounds | all p in \[0, 1\]; n\_answers equals questions\_per\_session (or 1 in binary mode) |
| Empirical check | records with p\_true near 0.7 show an observed mean within 0.03 of 0.7 at large N |
| Exact mode | labels equal predict\_recall(h\_true, delta) within 1e-9 |
| Irregular intervals | delta spans at least three orders of magnitude when configured |
| Cold start | the first session of each concept produces no record |
| Extreme histories | 500 sessions on one concept: no overflow, h stays inside bounds |
| Feature spec | records built with sqrt\_counts carry sqrt vectors in x\_before |

**Done when:** 50,000 records generate in under 30 seconds and the empirical-vs-true calibration check passes.

---

## Module 8: Trainer (AdaGrad, full paper loss)

**Prompt**

```text
[Shared context]
Create backend/hlr/trainer.py. This is the part the repo lacks entirely: nothing today learns theta.
train_hlr(examples, initial_theta, feature_spec, config) -> (CandidateArtifact, TrainingReport). It must not touch the active model or any repository.
Loss per example (ASSUMPTION: as summarised in the repo review of Settles & Meeder 2016; verify the form and the alpha and lambda values against the paper):
  z = theta . x;  h = 2 ** z;  p_hat = 2 ** (-delta / h)
  h_target = clip(-delta / log2(clip(p, p_min, p_max)), h_min, h_max)
  loss = (p - p_hat)^2 + alpha * (h - h_target)^2 + lambda * ||theta||^2
Gradient (use the UNCLIPPED h in the gradient; h_target is treated as a constant):
  d loss / d theta_j = [ 2 (p_hat - p) * p_hat * (ln 2)^2 * (delta / h) + 2 alpha (h - h_target) * h * ln 2 ] * x_j + 2 lambda * theta_j
Config: alpha, lambda (starting points such as alpha=0.01, lambda=0.1, then tune on validation), learning rate, epsilon, max_iterations, gradient clipping, option to exclude the bias from L2, optional per-example weights from n_answers, seed.
Optimizer: AdaGrad (accumulated squared gradients per parameter). Early stopping on the validation split the caller passes in.
The report records loss per iteration, gradient norm, convergence flag, the fraction of predictions at the half-life bounds, seed and full config. Raise a clear error on a non-finite loss.
Also write gradient_check(theta, examples, config) comparing the analytic gradient with central finite differences.
Write tests/test_trainer.py.
```

**Verification tests**

| Test | Expected |
| --- | --- |
| Gradient check, full loss | alpha=0.01, lambda=0.1: relative error below 1e-5 for every parameter at random thetas |
| Gradient check, special cases | alpha=0 and lambda=0 reduces to the plain squared error; check passes there too |
| Loss decreases | final training loss below the starting loss on simulated data |
| Recovery, exact labels | truth \[0, 1, -1\] (raw spec), about 20,000 records: each weight within 0.1 |
| Recovery, noisy labels | same truth with 5 questions per session: each weight within 0.3 |
| Recovery of the fake model's numbers | simulate with sqrt spec and truth \[0.15, 1.42, -1.18\], start from \[0, 1, -1\]: each weight within 0.2 |
| Beats the Leitner baseline | on held-out simulated data from that truth, trained MAE is lower than hlr\_v0\_fixed MAE |
| L2 effect | a large lambda gives a smaller |
| Boundary labels | p=0 and p=1 produce finite h\_target and finite gradients |
| Wrong feature spec | training sqrt-built data with the raw spec fails the recovery check, showing the spec matters |
| Reproducibility | same seed and data give identical theta |
| Non-finite guard | an injected NaN example raises a validation error |
| No side effects | the active model and global config are unchanged after training |
| Early stopping | validation loss stops improving and training halts before max\_iterations |

**Done when:** the gradient checks, exact-label recovery and beats-Leitner tests pass. Tune tolerances only after inspecting any failure.

---

## Module 9: Evaluation, baselines and leakage-safe splits

**Prompt**

```text
[Shared context]
Create backend/ml/dataset_builder.py and backend/hlr/evaluation.py.
dataset_builder: build an immutable, versioned dataset snapshot (id, row hash, created_at, filters) from training_records. Provide temporal_split(examples, cutoff) and student_holdout_split(examples, holdout_fraction, seed). Keep all rows of one student-concept-session together.
evaluation metrics, each with a bootstrap confidence interval resampled by student: MAE and RMSE on p, calibration table by predicted-probability bin, coverage, correlation between predicted and target half-life, AUC and Brier only when the labels are binary. Break results down by history length and delta range.
Baselines on the SAME examples: (1) hlr_v0_fixed, the Leitner-equivalent model the repo uses today; (2) constant probability (train mean); (3) historical accuracy n_right / (n_right + n_wrong), 0.5 if new.
evaluate_models(models, examples) returns one comparison report. Always name the prediction target next to a metric.
This module is the ONLY source of numbers that may appear in /api/models or any admin response.
Write tests/test_evaluation.py.
```

**Verification tests**

| Test | Expected |
| --- | --- |
| Perfect predictions | MAE = RMSE = 0 |
| Small hand-computed set | MAE and RMSE match exactly |
| Constant baseline | equals the train mean; its MAE is at least the true-theta HLR MAE on simulated data |
| Leitner baseline | hlr\_v0\_fixed scored through the same code path as any candidate |
| Temporal split | every test timestamp is later than every train timestamp |
| Student holdout | zero student overlap between train and test |
| Group integrity | no student-concept-session is split across sets |
| Same-example guarantee | all models score an identical set of example ids |
| Calibration | with the true theta on simulated data, bin means are within 0.05 of predicted |
| Snapshot immutability | same filters and data give the same hash; changed data gives a new hash |
| Bootstrap | the confidence interval narrows as data grows |
| Binary-only metrics | AUC and Brier are refused when labels are fractions |

**Done when:** on simulated data the true-theta model beats the constant, historical-accuracy and Leitner baselines on both held-out sets, and the leakage tests pass.

---

## Module 10: Model registry, promotion, rollback and shadow mode

**Prompt**

```text
[Shared context]
Create backend/ml/model_registry.py and backend/ml/promotion.py, and rebuild /api/models on top of them.
Seeding: on first start, register hlr_v0_fixed from the existing LAUNCH_THETA as the active model, with metrics null and status 'provisional_fixed_weights'. Delete the hard-coded model list in main.py, including the untrained hlr-trained-sqrt-v2.
register_candidate(artifact, report) stores theta, feature_spec, config, dataset_snapshot_id, metrics, checksum, status=candidate. It never activates.
load_active_model() verifies the checksum and that len(theta) equals the feature count, with a short TTL cache invalidated on activation. This replaces the direct use of LAUNCH_THETA in the pipeline.
promote(model_id, approver) runs gates: finite theta; held-out MAE not worse than the active model beyond a tolerance on BOTH temporal and student-holdout sets; a candidate must beat hlr_v0_fixed; calibration error within a limit; share of predictions at half-life bounds below a limit; data-readiness checks passed. Record every failure reason.
Activation is one transaction: deactivate the old model, activate the new one, mark concept_state rows stale or enqueue a recompute so states from different weights never mix.
rollback(to_model_id) reactivates an earlier version the same way.
Shadow mode: when a candidate exists, compute its predictions for every completed session next to the active model's, store them, and never use them for scheduling. Evaluation can then compare both on live data.
Write tests/test_registry.py.
```

**Verification tests**

| Test | Expected |
| --- | --- |
| Seeding | first start creates hlr\_v0\_fixed as the only active model with null metrics |
| `/api/models` | reads from the registry; numeric metrics appear only for models with an evaluation record |
| Register | candidate saved, active stays false, checksum stored |
| Tampered theta | load fails with a checksum error |
| Spec mismatch | theta of length 2 with a 3-feature spec rejected at registration |
| Gate failure | a candidate that does not beat hlr\_v0\_fixed is refused with reasons stored |
| Gate pass | a good candidate activates; exactly one active row |
| Atomicity | a crash mid-activation leaves the previous model active |
| Rollback | the previous model is active again with no retraining |
| State refresh | after activation, concept\_state rows are stale or recomputed under the new version |
| Shadow mode | shadow predictions are stored; the plan generated for a student is identical with and without a candidate |
| Authorization | a non-admin cannot promote (403) |
| Audit | every promote and rollback records approver, time and reasons |
| Legacy behaviour | with only hlr\_v0\_fixed registered, Module 0 snapshots still pass |

**Done when:** a full cycle works (v0 active, register v1, gates pass, activate, roll back to v0) and the fake metrics can no longer appear anywhere.

---

## Module 11: Scheduler integration

**Prompt**

```text
[Shared context]
If main.py already builds a study plan, move that logic into backend/scheduler/{candidate_selector,priority,plan_generator}.py behind the SAME endpoints and response shapes. If it does not, create them with GET /plan/today and GET /plan/week.
The scheduler only READS concept_state through get_concept_learning_state(student_id, concept_ids=None). It must not import the HLR predictor or recompute half-lives.
Inputs: recall_prob_now, next_review_at, is_new, subject_id, topic_id, difficulty, and user settings (daily minutes, subject priorities, exam dates).
Policy: select due concepts (next_review_at <= window end); split each day's minutes across subjects (weight by due count or 1 - mean recall); inside a subject order by lowest recall; cap new-concept slots; carry overflow to the next day; log the policy version and active model version on every plan.
Write tests/test_scheduler.py.
```

**Verification tests**

| Test | Expected |
| --- | --- |
| Due only | concepts with next\_review\_at in the future are excluded |
| Ordering | within a subject, lower recall comes first |
| Time budget | planned minutes never exceed the day's minutes |
| Overflow | excess due concepts appear on the next day, none dropped |
| New cap | never more new concepts than the configured cap |
| Subject fairness | a subject with zero due concepts gets no minutes |
| Exam boost | a nearer exam date raises that subject's share |
| State change | a wrong answer moves its concept earlier in the plan |
| Isolation | no import of the predictor or trainer in the scheduler package (checked via the import graph) |
| Audit | every plan stores policy and model version |
| Multi-tenant | student A never sees student B's concepts |
| Existing endpoints | response shapes match the Module 0 snapshots |

**Done when:** the end-to-end test in Module 13 shows the plan changing after a session.

---

## Module 12: Jobs, admin API and monitoring

**Prompt**

```text
[Shared context]
Create backend/jobs/{training_job,evaluation_job,monitoring_job}.py and backend/routers/admin_ml.py. Use APScheduler inside the FastAPI process for now.
Jobs run through a job_runs table with a unique (job_name, window) key, or a Postgres advisory lock, so two app instances never run the same job twice.
training_job: skip unless the data-readiness gate passes (enough independent students and examples, variation in delta and features, validation failure rate below a limit, duplicates below a limit). Train a candidate with trainer.py, register it as a candidate, never activate it.
monitoring_job: compute the share of half-lives at the bounds, non-finite predictions, duplicate-event rate, session validity rate, recall distribution and active model version; alert when thresholds are crossed.
Admin endpoints (admin role only): list models, list training runs, start a training run, activate, rollback.
Write tests/test_jobs_admin.py.
```

**Verification tests**

| Test | Expected |
| --- | --- |
| Two workers start the same job | one executes; the other exits cleanly |
| Insufficient data | status=skipped with a reason; no candidate created |
| Sufficient simulated data | candidate registered; active model unchanged |
| Dirty data | records failing validation above the limit cause a skip |
| Monitoring bound alert | states seeded at h\_max trigger an alert |
| Student token on admin routes | 403 on every admin endpoint |
| Activate via API | succeeds only when the gates passed; otherwise the response lists the reasons |
| Job failure | exception recorded in job\_runs; no partial model written |

**Done when:** the training job runs daily against a simulated database without ever changing the active model.

---

## Module 13: End-to-end acceptance test

**Prompt**

```text
[Shared context]
Write tests/e2e/test_hlr_closed_loop.py using the real FastAPI app and a PostgreSQL test database (REPO_BACKEND=postgres), plus a frontend smoke test.
Scenario with 2 subjects and 6 concepts:
1. Create a student, seed approved questions, set settings.
2. Run session 1 (first practice) and complete it. Jump time with the injectable clock (no sleep), run session 2, complete it.
3. Fetch the concept learning state and /plan/today.
4. Use the simulator to insert 20,000 training records, run the training job, confirm a candidate exists and the active model is unchanged.
5. Promote the candidate as admin, check concept states refresh, then roll back.
Frontend: a Vitest test that loads the API response for a concept and checks the JS fallback engine (calcHalfLife, calcRecallProb) agrees with the server value within 1e-9 for the active launch model.
Add the injectable clock to the app if Module 0 did not already.
```

**Verification checks**

| Check | Expected |
| --- | --- |
| Session 1 | state created, no training record |
| Session 2 | one training record per practiced concept with the correct x\_before |
| Retry of complete | no change |
| Wrong answers | half-life shortens and the concept moves earlier in the plan |
| Right answers | half-life lengthens and next\_review\_at moves later |
| Legacy parity | with only hlr\_v0\_fixed active, half-lives equal what the original main.py would have produced |
| Training job | candidate registered; active model unchanged |
| Promote and rollback | the active pointer switches and returns; every record carries its model version |
| Frontend parity | JS engine and server agree on half-life and recall |
| Tenant isolation | a second student sees none of the first student's data |

**Done when:** this test passes in CI from a clean database.

---

## Module 14: Difficulty feature (after the closed loop works)

The `difficulty` field exists in the data model but never affects the half-life, so a Hard concept is treated like an Easy one. This module adds it as a new feature spec, which can only go live through the registry gates.

**Prompt**

```text
[Shared context]
Add a feature spec 'sqrt_counts_difficulty' to backend/hlr/features.py: x = [1, sqrt(n_right), sqrt(n_wrong), difficulty_score] with Easy = -1, Medium = 0, Hard = +1 (so the bias stays the Medium baseline). Unknown or missing difficulty maps to 0 and is counted in a data-quality metric.
extract_features gains an optional context argument carrying difficulty; older specs ignore it and keep producing the same vectors.
Store difficulty in training_records.x_before at the time of the session, so later edits to a concept's difficulty cannot rewrite history.
Extend the simulator with a true difficulty weight and the trainer needs no change beyond the longer theta.
The new spec must never be activated directly: it goes through register_candidate and promote like any other model, and must beat the best 3-feature model on held-out data.
Write tests/test_difficulty_feature.py.
```

**Verification tests**

| Test | Expected |
| --- | --- |
| New vector | 3 right, 1 wrong, Hard gives \[1, 1.7320508, 1, 1\] |
| Older specs | raw\_counts and sqrt\_counts vectors identical to before for every input |
| Spec hash | differs from sqrt\_counts |
| Theta length | a 3-weight theta with the 4-feature spec is rejected at registration |
| History safety | changing a concept's difficulty later does not change stored x\_before |
| Recovery | simulate with a true difficulty weight of -0.5: the trainer recovers it within 0.15 |
| Value of the feature | on data where Hard concepts decay faster, the 4-feature model beats the 3-feature model on held-out MAE |
| No value | on data without a difficulty effect, the gate does not promote it |
| Missing difficulty | maps to 0 and increments the data-quality counter |

**Done when:** the registry can hold both specs side by side and a difficulty model only becomes active by passing the same gates as any other candidate.

---

## Suggested run order and CI

| Order | Modules | Notes |
| --- | --- | --- |
| 1 | 0 | First, touches no logic; freezes current behaviour |
| 2 | 1, 2, 3 | Extraction; run the Module 0 snapshots after each one |
| 3 | 4, 5, 6 | Persistence and the session pipeline; 4 before 5 and 6 |
| 4 | 7, 8, 9 | Need only modules 1 to 3, so they can start while 4 to 6 are in review |
| 5 | 10, 11, 12 | After 6 and 9 |
| 6 | 13, then 14 | Closed-loop acceptance test, then the difficulty feature |

CI gates on every pull request: the Module 0 characterization snapshots and the shared test-vector file under both pytest and Vitest (seconds, no database); unit tests for modules 1 to 3; PostgreSQL integration tests for modules 4 to 6 and the repository contract suite on both backends; simulation and gradient tests for 7 to 9 (mark slow ones with `@pytest.mark.slow` and run nightly); the end-to-end test before merging to main.

## Four things to decide before Module 8

1. **Confirm the loss and its weights.** The review gives the paper's loss as the squared recall error plus a half-life error term (alpha) plus an L2 penalty (lambda). Check that form and the alpha and lambda starting values against the paper before trusting Module 8's results.
2. **Fix the delta convention.** The prompts measure delta from the previous session's completion. If you want per-answer timestamps instead, Modules 6, 7 and 8 change together.
3. **Decide what a label is.** The review notes that the paper's observed recall is a single outcome or a lag-bin proportion, while the repo has a session fraction. The prompts keep the fraction with n\_answers stored; the simulator's binary mode lets you test both.
4. **Confirm there is no database yet.** Module 4 assumes the in-memory lists are the only storage. If a database exists, say so and Module 4 shrinks to a migration.
