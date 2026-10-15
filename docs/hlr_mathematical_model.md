# Half-Life Regression (HLR) Mathematical Specification

## 1. Introduction & Background

Spaced repetition systems (SRS) are grounded in cognitive psychology, dating back to **Hermann Ebbinghaus (1885)**, who demonstrated that memory retention decays exponentially over time in the absence of active reinforcement.

Historically, learning software used heuristic rule-based systems:
- **The Leitner System (1972)**: Physical flashcards sorted into discrete boxes with fixed review intervals (e.g., 1 day, 3 days, 7 days, 14 days).
- **SuperMemo SM-2 (Wozniak, 1987)**: The algorithm behind Anki, which assigns each item an "Easiness Factor" ($EF$) and computes fixed multiplier jumps:
  $$I(1) = 1, \quad I(2) = 6, \quad I(n) = I(n-1) \times EF$$
  where $EF$ is manually updated by the user rating their recall on a subjective 0–5 scale.

### The Breakthrough: Settles & Meeder (Duolingo, ACL 2016)
In their seminal paper *"A Trainable Spaced Repetition Model for Language Learning"*, **Burr Settles and Brenda Meeder** formulated **Half-Life Regression (HLR)**. Instead of discrete heuristics or subjective user ratings, HLR models memory half-life as an empirical function of observed study history using machine learning.

FocusFlow implements Settles & Meeder's HLR formulation directly in [backend/app/services/hlr.py](file:///d:/Github%20repositories/FocusFlow/backend/app/services/hlr.py) and [frontend/src/hlr.js](file:///d:/Github%20repositories/FocusFlow/frontend/src/hlr.js).

---

## 2. Core Mathematical Formulations

### 2.1 The Forgetting Curve
The probability $p$ that a learner can successfully recall a concept after an elapsed interval $\Delta$ (measured in days) is governed by an exponential decay function parameterized by the concept's **half-life** $h$:

$$p = 2^{-\frac{\Delta}{h}}$$

Where:
- $\Delta \ge 0$: Elapsed time (in days) since the student last practiced the concept.
- $h > 0$: The **half-life** of the concept in memory, defined as the time window required for the probability of recall to drop to exactly $50\%$ ($2^{-1} = 0.5$).
- When $\Delta = 0$ (immediately after practice): $p = 2^0 = 1.0$ ($100\%$ recall).
- When $\Delta = h$: $p = 2^{-1} = 0.5$ ($50\%$ recall).
- When $\Delta = 2h$: $p = 2^{-2} = 0.25$ ($25\%$ recall).

```
Recall Probability (p)
1.0 |========\
0.8 |         \
0.7 |----------\--------- [Review Threshold τ = 0.70]
0.6 |           \
0.5 |------------\------- [Half-Life h: p = 0.50]
0.2 |             \
0.0 +-----------------------------------> Time Elapsed (Δ)
    0            Δ_review  h
```

---

### 2.2 Half-Life Estimation Equation
HLR models the half-life $h$ as a log-linear function of a feature vector $\mathbf{x} \in \mathbb{R}^D$ and a learnable weight vector $\boldsymbol{\theta} \in \mathbb{R}^D$:

$$h = 2^{\boldsymbol{\theta}^T \mathbf{x}} = 2^{\sum_{j=0}^{D-1} \theta_j x_j}$$

Because half-life is strictly positive ($h > 0$), exponentiating with base 2 guarantees a positive value while maintaining a direct, intuitive relationship with doubling times.

---

### 2.3 Feature Representation $\mathbf{x}$
For each user-concept interaction, FocusFlow constructs a feature vector $\mathbf{x}$:

#### 1. Baseline Model (`raw_counts`):
$$\mathbf{x} = \begin{bmatrix} 1 \\ n_{\text{correct}} \\ n_{\text{incorrect}} \end{bmatrix}$$

- $x_0 = 1.0$: Intercept / bias term representing the baseline memory half-life of an unfamiliar concept.
- $x_1 = n_{\text{correct}}$: Total cumulative count of successful recall events.
- $x_2 = n_{\text{incorrect}}$: Total cumulative count of failed recall events.

#### 2. Diminishing Returns Model (`sqrt_counts`):
To model the psychological principle of diminishing marginal sensitivity (each additional repetition provides slightly less marginal gain than the previous one), the feature counts can be square-root transformed:

$$\mathbf{x} = \begin{bmatrix} 1 \\ \sqrt{n_{\text{correct}}} \\ \sqrt{n_{\text{incorrect}}} \end{bmatrix}$$

---

### 2.4 The Intuition of Launch Weights $\boldsymbol{\theta}_{\text{launch}}$
FocusFlow initializes the model with cold-start weights derived from Leitner box dynamics:

$$\boldsymbol{\theta}_{\text{launch}} = \begin{bmatrix} 1.0 \\ 1.0 \\ -1.0 \end{bmatrix}$$

Let us analyze the algebraic behavior of these weights:

$$h = 2^{1.0 \times 1 + 1.0 \times n_{\text{correct}} - 1.0 \times n_{\text{incorrect}}} = 2^{1 + n_{\text{correct}} - n_{\text{incorrect}}}$$

1. **Brand-New Concept** ($n_{\text{correct}} = 0, n_{\text{incorrect}} = 0$):
   $$h = 2^{1 + 0 - 0} = 2^1 = 2.0 \text{ days}$$
   A newly introduced concept defaults to a 48-hour half-life.

2. **Correct Recall Effect** ($n_{\text{correct}} \to n_{\text{correct}} + 1$):
   $$h_{\text{new}} = 2^{1 + (n_c + 1) - n_i} = 2 \times 2^{1 + n_c - n_i} = 2 \times h_{\text{old}}$$
   *A correct answer doubles the concept's half-life in memory.* This reproduces Leitner's box progression continuously without rigid box thresholds.

3. **Incorrect Recall Effect** ($n_{\text{incorrect}} \to n_{\text{incorrect}} + 1$):
   $$h_{\text{new}} = 2^{1 + n_c - (n_i + 1)} = 2^{-1} \times 2^{1 + n_c - n_i} = 0.5 \times h_{\text{old}}$$
   *An incorrect answer cuts the concept's half-life in half.*

---

## 3. Review Scheduling Mathematics

To ensure long-term retention without over-studying, the system must trigger a review when the predicted recall probability drops to a target retention threshold $\tau \in (0, 1)$ (by default, $\tau = 0.70$ or $70\%$ retention).

We solve for the elapsed review interval $\Delta^*$ at which $p(\Delta^*) = \tau$:

$$\tau = 2^{-\frac{\Delta^*}{h}}$$

Taking the base-2 logarithm of both sides:

$$\log_2(\tau) = -\frac{\Delta^*}{h}$$

Multiplying by $-h$:

$$\Delta^* = -h \log_2(\tau)$$

### Numerical Example with $\tau = 0.70$:
$$\log_2(0.70) = \frac{\ln(0.70)}{\ln(2)} \approx \frac{-0.35667}{0.69315} \approx -0.514573$$

$$\Delta^* = -h \times (-0.514573) \approx 0.5146 \times h$$

Therefore:
- If a concept has a half-life of $h = 4.0\text{ days}$, it should be reviewed at $\Delta^* = 4.0 \times 0.5146 \approx 2.06\text{ days}$.
- If a concept has a half-life of $h = 10.0\text{ days}$, it should be reviewed at $\Delta^* \approx 5.15\text{ days}$.
- If the student desires higher retention (e.g., $\tau = 0.85$ before an exam):
  $$\log_2(0.85) \approx -0.234 \implies \Delta^* \approx 0.234 \times h$$
  The review interval contracts automatically, prompting more frequent reviews.

---

## 4. Boundary Conditions & Numerical Clamping

In floating-point computation, unconstrained exponentiation can produce arithmetic overflows, underflows, or zero division. FocusFlow strictly enforces the empirical bounds established by Duolingo:

| Parameter | Minimum Value | Maximum Value | Rationale |
| :--- | :--- | :--- | :--- |
| **Half-Life ($h$)** | $h_{\min} = \frac{15}{1440} \approx 0.0104\text{ days}$ (15 minutes) | $h_{\max} = 270.0\text{ days}$ (~9 months) | Prevents runaway exponential explosion or zero-interval lockups. |
| **Recall Prob ($p$)** | $p_{\min} = 0.0001$ ($0.01\%$) | $p_{\max} = 0.9999$ ($99.99\%$) | Prevents $\log(0)$ and extreme asymptote saturation. |
| **Linear Combination** | $\boldsymbol{\theta}^T \mathbf{x} \ge -10.0$ | $\boldsymbol{\theta}^T \mathbf{x} \le 12.0$ | Clamps $2^{\boldsymbol{\theta}^T \mathbf{x}}$ within $[2^{-10}, 2^{12}] = [0.00097, 4096]$. |

```python
# Code snippet from backend/app/services/hlr.py
H_MIN: float = 15.0 / 1440.0   # 15 minutes in days
H_MAX: float = 270.0           # ~9 months

def half_life(theta: list[float], x: list[float]) -> float:
    linear_comb = sum(t * v for t, v in zip(theta, x))
    if linear_comb > 12.0:
        h = H_MAX
    elif linear_comb < -10.0:
        h = H_MIN
    else:
        h = 2.0 ** linear_comb
    return float(min(max(h, H_MIN), H_MAX))
```

---

## 5. Model Training & Parameter Optimization

When students complete practice sessions, observed retention events are recorded in the `training_records` table:

$$\mathcal{D} = \{ (\mathbf{x}_k, \Delta_k, y_k) \}_{k=1}^N$$

Where:
- $\mathbf{x}_k$: Feature vector before the session.
- $\Delta_k$: Time elapsed (in days) since previous review.
- $y_k \in [0, 1]$: Observed recall rate in the session (e.g., $y_k = \frac{\text{correct attempts}}{\text{total attempts}}$).

### 5.1 Loss Function
Settles & Meeder utilize a composite squared-error loss function over the predicted probability $\hat{p}_k$:

$$\mathcal{L}(\boldsymbol{\theta}) = \frac{1}{2} \sum_{k=1}^N \left( y_k - \hat{p}_k \right)^2 + \frac{\lambda}{2} \|\boldsymbol{\theta}\|_2^2$$

Where:
$$\hat{p}_k = 2^{-\frac{\Delta_k}{h_k}} = 2^{-\Delta_k 2^{-\boldsymbol{\theta}^T \mathbf{x}_k}}$$

### 5.2 Gradient Calculation
Applying the chain rule:

$$\frac{\partial \mathcal{L}_k}{\partial \theta_j} = -(y_k - \hat{p}_k) \frac{\partial \hat{p}_k}{\partial \theta_j}$$

Using the identity $\frac{d}{du}(2^u) = 2^u \ln(2)$:

$$\frac{\partial \hat{p}_k}{\partial \theta_j} = \hat{p}_k \ln(2) \left( \frac{\Delta_k}{h_k} \right) \ln(2) x_{k,j} = \hat{p}_k (\ln 2)^2 \frac{\Delta_k}{h_k} x_{k,j}$$

Substituting back into the gradient:

$$\frac{\partial \mathcal{L}_k}{\partial \theta_j} = -(y_k - \hat{p}_k) \hat{p}_k (\ln 2)^2 \frac{\Delta_k}{h_k} x_{k,j} + \lambda \theta_j$$

### 5.3 Online AdaGrad Optimizer
Weights are updated using **AdaGrad** (Adaptive Gradient Algorithm) to adjust individual learning rates per feature dimension based on historical gradient norms:

$$G_{j, t} = G_{j, t-1} + \left( \frac{\partial \mathcal{L}}{\partial \theta_j} \right)^2$$

$$\theta_{j, t} = \theta_{j, t-1} - \frac{\eta}{\sqrt{G_{j, t} + \epsilon}} \frac{\partial \mathcal{L}}{\partial \theta_j}$$

---

## 6. Algorithm Comparison Matrix

| Feature | Leitner Box System | SuperMemo SM-2 (Anki) | FocusFlow HLR |
| :--- | :--- | :--- | :--- |
| **Foundation** | Physical card bins (1972) | Heuristic formulas (1987) | Empirical ML on 100M+ trials (Settles 2016) |
| **Interval Progression** | Fixed integer steps (1, 3, 7, 14 days) | Multiplied by subjective $EF$ | Continuous function of elapsed time $\Delta$ and $h$ |
| **Review Feedback** | Binary (Pass / Fail) | Subjective 0–5 scale ("Again, Hard, Good, Easy") | Objective test accuracy ($\frac{\text{correct}}{\text{total}}$) |
| **Mathematical Soundness** | None (heuristic) | Empirical curve fitting | Exponential forgetting curve ($p = 2^{-\Delta/h}$) |
| **Personalization** | Universal fixed buckets | Item-level factor | User-concept parameter estimation |
| **Target Retention** | Uncontrollable | Indirect (~85-90%) | Explicit mathematical threshold ($\tau = -h \log_2 p$) |
