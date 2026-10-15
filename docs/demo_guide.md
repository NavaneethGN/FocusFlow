# FocusFlow Demo & Presentation Guide

## 1. Executive Summary

This guide provides a structured, step-by-step walkthrough for demonstrating **FocusFlow** to professors, technical evaluators, or project reviewers. It includes a recommended 8–10 minute presentation narrative, specific user actions, key talking points, and an evaluator Q&A defense cheat sheet.

---

## 2. Pre-Demo Setup Checklist

Ensure both services are running locally before starting your presentation:

1. **Backend Service** (Port 8000):
   ```bash
   cd backend
   .venv\Scripts\activate
   uvicorn main:app --reload --port 8000
   ```
   - Verify health: Open [http://localhost:8000/docs](http://localhost:8000/docs) in your browser.

2. **Frontend Service** (Port 5173):
   ```bash
   cd frontend
   npm run dev
   ```
   - Verify app: Open [http://localhost:5173](http://localhost:5173).

3. **Gemini API Key**:
   - Ensure your `backend/.env` file contains `GEMINI_API_KEY=your_key_here`.
   - The UI will display a green `Live AI Mode` indicator in the AI tabs.

---

## 3. Demo Walkthrough Narrative (8-Minute Script)

### Step 1: The Problem & The Solution (1 Minute)
- **What to show**: Land on the **Dashboard** (`http://localhost:5173`).
- **Talking Point**:
  > *"Most study apps like Anki rely on the 1987 SM-2 algorithm or physical Leitner boxes, which use subjective ratings like 'Hard' or 'Easy' and rigid integer day multipliers. FocusFlow replaces heuristics with **Half-Life Regression (HLR)**, an empirical machine learning model published by Duolingo researchers at ACL 2016. It predicts the continuous probability of memory decay using actual test outcomes and adjusts intervals using exponential decay."*

### Step 2: Dashboard & Cognitive Readiness (1.5 Minutes)
- **What to show**:
  1. Highlight the **Overall Readiness Metric** (e.g., $78\%$).
  2. Point out the **Critical Concepts Alert** banner (concepts with recall probability $p < 0.50$ requiring urgent review).
  3. Click on the **3D Interactive Flashcards** deck to flip between concept definitions and memory formulas.
- **Talking Point**:
  > *"The system aggregates memory retention across all enrolled courses in real time. Rather than cramming everything, the student immediately sees which concepts are vulnerable to forgetting right now."*

### Step 3: Active Quiz Arena & Mathematical Updating (2 Minutes)
- **What to show**:
  1. Click **"Quick Practice"** or navigate to the **Active Quiz** tab.
  2. Answer a multiple-choice question correctly (e.g., *Scaled Dot-Product Attention*).
  3. Observe the immediate pedagogical explanation.
  4. Submit a question incorrectly (e.g., *A\* Heuristic Admissibility*).
  5. Click **"Finish Session"**.
- **Talking Point**:
  > *"Each submission is sent to the FastAPI backend with an idempotent UUID token. When the session closes, the HLR engine calculates the session recall rate and updates the concept's half-life: correct answers double the half-life ($2^{\theta_1}$), while incorrect answers halve it ($2^{\theta_2}$). The database simultaneously records this event in `training_records` for offline model training."*

### Step 4: The Forgetting Curve Visualizer (1.5 Minutes)
- **What to show**:
  1. Switch to the **Forgetting Curve** tab.
  2. Select *Backpropagation & Chain Rule*.
  3. Drag the **Target Retention Threshold ($\tau$)** slider from $0.70$ to $0.85$.
  4. Move the **$n_{\text{correct}}$** and **$n_{\text{incorrect}}$** sliders to demonstrate how the curve flattens or steepens in real time.
- **Talking Point**:
  > *"Here you can see the mathematical realization of Ebbinghaus's exponential forgetting curve: $p = 2^{-\Delta/h}$. The review point is mathematically calculated as $\Delta^* = -h \log_2(\tau)$. If the student sets a higher retention target before an exam, the recommended review interval automatically contracts."*

### Step 5: Adaptive Study Plan (1 Minute)
- **What to show**:
  1. Switch to the **Study Plan** tab.
  2. Show how the algorithm divides the student's daily 60-minute budget into focused 15-minute study blocks.
- **Talking Point**:
  > *"The scheduler sorts concepts in ascending order of recall probability $p$, ensuring that high-risk concepts are prioritized before the student's daily time budget is exhausted."*

### Step 6: Generative AI Tutoring Suite (2 Minutes)
- **What to show**:
  1. **Socratic Study Buddy** (`Chat` tab):
     - Click the quick prompt: *"Explain backpropagation intuitively"*.
     - Show how the AI provides a guiding explanation without spoiling quiz solutions.
  2. **Deep Doubt Solver** (`Doubts` tab):
     - Enter a doubt: *"Why do we need virtual memory if RAM is fast?"*
     - Click **"Solve Doubt"**.
     - Highlight the four distinct output cards: *Core Clarification*, *Real-World Analogy*, *Common Misconception*, and *Check Question*.
  3. **Mnemonic Laboratory** (`Mnemonics` tab):
     - Select *Deadlock Coffman Conditions* and click **"Generate Mnemonics"**.
     - Showcase the *Acronym* (e.g., **M-H-N-C**), *Visual Story*, and *Rhyme*.
- **Talking Point**:
  > *"FocusFlow uses Google Gemini with structured system prompts. We don't just dump raw text; we structure learning into cognitive anchors and Socratic dialogues that reinforce retention."*

### Step 7: Time-Travel Virtual Clock Simulation (1 Minute)
- **What to show**:
  1. Navigate to the **Settings** tab.
  2. Under **Virtual Simulation Clock**, click **"Advance +5 Days"**.
  3. Return to the **Dashboard**.
  4. Observe how the Overall Readiness has decayed and previously stable concepts are now marked **Critical**.
- **Talking Point**:
  > *"To validate our memory models, we built a virtual simulation clock. Advancing time lets evaluators verify how the forgetting curve decays continuously without having to wait days in real life."*

---

## 4. Evaluator Q&A Defense Guide

### Q1: How does Half-Life Regression differ from Anki's SM-2 algorithm?
> **Answer**: *"SM-2 requires the user to subjectively self-grade their recall on a 0–5 scale ('Again, Hard, Good, Easy') and relies on fixed multiplier heuristics. HLR removes subjectivity: it computes half-life $h = 2^{\boldsymbol{\theta}^T \mathbf{x}}$ directly from objective test results ($n_{\text{correct}}, n_{\text{incorrect}}$) and continuously predicts recall probability $p = 2^{-\Delta/h}$ using a validated exponential decay function."*

### Q2: Why is the model formulated with base 2 instead of the natural constant $e$?
> **Answer**: *"Base 2 makes the mathematical weights directly interpretable in terms of doubling times. For our launch weights $\boldsymbol{\theta} = [1, 1, -1]$, a correct answer increments the exponent by $+1$, which exactly doubles the half-life ($2^1 = 2$). An incorrect answer decrements the exponent by $-1$, exactly halving the half-life ($2^{-1} = 0.5$). This provides a continuous, elegant equivalent of Leitner box transitions."*

### Q3: How do you handle cold-start for a brand-new concept?
> **Answer**: *"For a new concept where $n_{\text{correct}} = 0$ and $n_{\text{incorrect}} = 0$, the feature vector is $\mathbf{x} = [1, 0, 0]^T$. With bias weight $\theta_0 = 1.0$, the baseline half-life evaluates to $h = 2^{1.0} = 2.0\text{ days}$. The student is scheduled for an initial review within approximately 24 hours based on the $70\%$ threshold."*

### Q4: What happens if the Gemini AI service is down or unconfigured?
> **Answer**: *"FocusFlow is designed with graceful degradation. The entire HLR mathematical engine, quiz scoring, session tracking, and dashboard operate locally on FastAPI and SQLite. If Gemini is unreachable or no API key is provided, the AI endpoints seamlessly switch to curated pedagogical fallbacks from our local knowledge base without throwing errors."*

### Q5: How do you prevent duplicate score submissions over slow networks?
> **Answer**: *"The frontend generates a unique UUID `event_id` for every quiz question response. The backend enforces a unique database constraint on `Attempt.event_id`. If a student double-clicks or the network retries a POST request, the database rejects the duplicate attempt, maintaining mathematical consistency."*

---

## 5. Troubleshooting Reference

| Symptom | Cause | Resolution |
| :--- | :--- | :--- |
| **Port 8000 already in use** | A dangling Python process is running. | Run `netstat -ano \| findstr 8000` and kill the PID with `taskkill /PID <PID> /F`. |
| **Port 5173 already in use** | Previous Vite instance running. | Vite will automatically switch to 5174; check the terminal output for the active URL. |
| **AI Status shows "Offline Mode"** | `GEMINI_API_KEY` missing from `.env`. | Add your Gemini key to `backend/.env` as `GEMINI_API_KEY=AIzaSy...` and refresh the page. |
| **Database out of sync** | Schema modifications during testing. | Delete `backend/focusflow.db` and restart `uvicorn` to auto-reseed fresh data. |
