# Design Phase

## ✅ 1. System Architecture (VERY IMPORTANT)


```
User (Student)
      ↓
Frontend (React UI)
      ↓
Backend API (Node)
      ↓
AI Engine (Scheduler Logic)
      ↓
Database (User Data + Tasks)
```


> “We are following a modular architecture separating UI, logic, and AI scheduling engine.”

---

## ✅ 2. Core Modules (Write This)

Divide system into 5 parts :

1. **User Input Module**

   * subjects, deadlines, hours, difficulty

2. **Scheduler Engine (MAIN AI PART)**

   * priority calculation
   * time allocation

3. **Constraint Handler**

   * max hours/day
   * deadlines

4. **Adaptive Module**

   * reschedules if tasks missed

5. **Visualization Module**

   * timetable display


---

## ✅ 3. Basic Algorithm (MOST IMPORTANT AI PART)


### 🔹 Step-Based Logic

```
1. Take input (subjects, deadlines, difficulty, hours)
2. Assign priority score:
   Priority = (Deadline weight + Difficulty weight)

3. Sort subjects based on priority

4. Allocate study slots:
   - Divide total hours
   - Assign more time to high priority subjects

5. Generate timetable

6. If task missed:
   - Recalculate priorities
   - Regenerate schedule
```

“This is a heuristic-based scheduling approach.”

---

## ✅ 4. Sample Input & Output (SHOW THIS)

### Input:

* Math → 3 days → Hard
* OS → 5 days → Medium
* AI → 2 days → Hard

### Output:

```
Day 1 → AI, Math
Day 2 → AI, Math
Day 3 → Math, OS
Day 4 → OS
Day 5 → OS
```

## ✅ 5. Database Design (Simple)

Show 2 tables:

### Users

* user_id
* name

### Tasks

* task_id
* subject
* deadline
* difficulty
* status

---

## ✅ 6. Tech Stack (Say This Clearly)

* Frontend → React
* Backend → Node
* Database → MongoDB
* AI Logic → Python

---

## ✅ 7. One Line “AI Justification” (IMPORTANT)

“We model the problem as a constraint-based scheduling and optimization problem using heuristic techniques.”

