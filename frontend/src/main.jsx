import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  CalendarDays,
  Check,
  Clock3,
  Focus,
  Plus,
  RefreshCw,
  Sparkles,
  Target,
  Trash2,
  X,
} from "lucide-react";
import "./styles.css";

const API_URL = "http://localhost:8000/api";
const starterTasks = [
  {
    id: 1,
    subject: "Artificial Intelligence",
    deadline_days: 2,
    difficulty: "Hard",
    status: "In progress",
  },
  {
    id: 2,
    subject: "Operating Systems",
    deadline_days: 5,
    difficulty: "Medium",
    status: "Planned",
  },
  {
    id: 3,
    subject: "Mathematics",
    deadline_days: 3,
    difficulty: "Hard",
    status: "Planned",
  },
];
const starterSlots = [
  { day: 0, start: "09:00", end: "11:00" },
  { day: 0, start: "17:00", end: "20:00" },
  { day: 1, start: "09:00", end: "11:00" },
  { day: 1, start: "18:00", end: "20:00" },
  { day: 2, start: "17:00", end: "20:00" },
  { day: 3, start: "09:00", end: "11:00" },
  { day: 4, start: "17:00", end: "20:00" },
];

function App() {
  const [tasks, setTasks] = useState(starterTasks);
  const [availableSlots, setAvailableSlots] = useState(starterSlots);
  const [schedule, setSchedule] = useState(null);
  const [view, setView] = useState("today");
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [clock, setClock] = useState(new Date());
  const [form, setForm] = useState({
    subject: "",
    deadline_days: 3,
    difficulty: "Medium",
    status: "Planned",
  });
  const [slotForm, setSlotForm] = useState({
    day: 0,
    start: "09:00",
    end: "11:00",
  });

  useEffect(() => {
    generateSchedule();
  }, []);

  useEffect(() => {
    const timer = setInterval(() => setClock(new Date()), 30000);
    return () => clearInterval(timer);
  }, []);

  async function generateSchedule() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_URL}/schedule`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tasks,
          available_slots: availableSlots,
          locked_schedule: currentSchedule.filter(
            (item) => item.status === "Completed",
          ),
        }),
      });
      if (!response.ok)
        throw new Error("The scheduler could not process these tasks.");
      setSchedule(await response.json());
    } catch (requestError) {
      setError("Start the Python API on port 8000 to generate your plan.");
    } finally {
      setLoading(false);
    }
  }

  function addTask(event) {
    event.preventDefault();
    setTasks((current) => [
      ...current,
      {
        ...form,
        id: Date.now(),
        deadline_days: Number(form.deadline_days),
      },
    ]);
    setForm({
      subject: "",
      deadline_days: 3,
      difficulty: "Medium",
      status: "Planned",
    });
    setShowForm(false);
  }

  function updateStatus(id, status) {
    setTasks((current) =>
      current.map((task) => (task.id === id ? { ...task, status } : task)),
    );
  }

  function addSlot(event) {
    event.preventDefault();
    setAvailableSlots((current) => [
      ...current,
      { ...slotForm, day: Number(slotForm.day) },
    ]);
  }

  function updateScheduleStatus(item, status) {
    if (status === "Completed") {
      setTasks((current) =>
        current.map((task) =>
          task.subject === item.subject ? { ...task, status } : task,
        ),
      );
    } else if (status === "Missed") {
      setTasks((current) =>
        current.map((task) =>
          task.subject === item.subject ? { ...task, status } : task,
        ),
      );
    }
    setSchedule((current) =>
      current
        ? {
            ...current,
            schedule: current.schedule.map((entry) =>
              entry.day === item.day &&
              entry.start === item.start &&
              entry.end === item.end &&
              entry.subject === item.subject
                ? { ...entry, status }
                : entry,
            ),
          }
        : current,
    );
  }

  function slotHasPassed(item) {
    if (item.day !== 0) return false;
    const now = new Date();
    const [hours, minutes] = item.end.split(":").map(Number);
    return (
      now.getHours() > hours ||
      (now.getHours() === hours && now.getMinutes() >= minutes)
    );
  }

  const currentSchedule = useMemo(
    () =>
      schedule?.schedule.map((item) => ({
        ...item,
        status:
          !["Missed", "Completed"].includes(item.status) && slotHasPassed(item)
            ? "Completed"
            : item.status,
      })) || [],
    [schedule, clock],
  );
  const visibleSchedule = currentSchedule.filter(
    (item) => view === "week" || item.day === 0,
  );
  const groupedSchedule =
    visibleSchedule.reduce((groups, item) => {
      groups[item.day] = [...(groups[item.day] || []), item];
      return groups;
    }, {}) || {};
  const completedTasks = tasks.filter(
    (task) => task.status === "Completed",
  ).length;

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">
            <Focus size={18} />
          </span>
          <span>FocusFlow</span>
        </div>
        <div className="header-note">
          <span className="live-dot" /> Heuristic engine online{" "}
          <span className="divider" /> Semester 5
        </div>
      </header>

      <section className="hero">
        <div>
          <p className="eyebrow">
            <Sparkles size={14} /> AI study planner
          </p>
          <h1>
            Make room for
            <br />
            <em>what matters.</em>
          </h1>
          <p className="hero-copy">
            A calm, adaptive plan for deadlines that refuse to sit still.
          </p>
        </div>
        <div className="hero-date">
          <span>Today</span>
          <strong>
            {new Date().toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
            })}
          </strong>
        </div>
      </section>

      <section className="stats-grid">
        <Stat
          icon={<Clock3 size={17} />}
          label="Assigned slots"
          value={`${schedule?.scheduled_slots || 0}`}
          note="slots assigned"
        />
        <Stat
          icon={<Target size={17} />}
          label="Coverage"
          value={`${schedule?.completion_percent || 0}%`}
          note="of available slots"
          accent
        />
        <Stat
          icon={<Check size={17} />}
          label="Completed"
          value={`${completedTasks}/${tasks.length}`}
          note="tasks checked off"
        />
        <div className="capacity-card">
          <div>
            <span className="stat-label">Available slots</span>
            <strong>{availableSlots.length}</strong>
          </div>
          <span className="capacity-note">
            {availableSlots.filter((slot) => slot.day === 0).length} slots today
          </span>
          <CalendarDays size={30} color="#529578" />
        </div>
      </section>

      <div className="workspace-grid">
        <section className="panel tasks-panel">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">01 / INPUT</p>
              <h2>Your subjects</h2>
            </div>
            <button
              className="icon-button"
              onClick={() => setShowForm(true)}
              title="Add subject"
            >
              <Plus size={18} />
            </button>
          </div>
          <p className="panel-intro">
            Set the context. FocusFlow will handle the trade-offs.
          </p>
          <div className="task-list">
            {tasks.map((task) => (
              <TaskRow
                key={task.id}
                task={task}
                onDelete={() =>
                  setTasks(tasks.filter((item) => item.id !== task.id))
                }
                onStatus={(status) => updateStatus(task.id, status)}
              />
            ))}
          </div>
          {showForm && (
            <form className="add-form" onSubmit={addTask}>
              <div className="form-head">
                <span>Add a subject</span>
                <button
                  type="button"
                  className="plain-button"
                  onClick={() => setShowForm(false)}
                >
                  <X size={16} />
                </button>
              </div>
              <input
                required
                placeholder="Subject name"
                value={form.subject}
                onChange={(event) =>
                  setForm({ ...form, subject: event.target.value })
                }
              />
              <div className="form-row">
                <label>
                  Due in days
                  <input
                    type="number"
                    min="1"
                    max="30"
                    value={form.deadline_days}
                    onChange={(event) =>
                      setForm({ ...form, deadline_days: event.target.value })
                    }
                  />
                </label>
                <label>
                  Study time
                  <input disabled value="From slots" />
                </label>
              </div>
              <label>
                Difficulty
                <select
                  value={form.difficulty}
                  onChange={(event) =>
                    setForm({ ...form, difficulty: event.target.value })
                  }
                >
                  <option>Easy</option>
                  <option>Medium</option>
                  <option>Hard</option>
                </select>
              </label>
              <button className="submit-button">
                Add to plan <Plus size={15} />
              </button>
            </form>
          )}
          <button className="add-subject" onClick={() => setShowForm(true)}>
            <Plus size={16} /> Add another subject
          </button>
          <div className="availability-heading">
            <span className="section-kicker">AVAILABLE TIME SLOTS</span>
            <span>{availableSlots.length} total</span>
          </div>
          <div className="slot-list">
            {availableSlots.map((slot, index) => (
              <div
                className="slot-chip"
                key={`${slot.day}-${slot.start}-${index}`}
              >
                <Clock3 size={13} />{" "}
                {slot.day === 0 ? "Today" : `Day ${slot.day + 1}`} ·{" "}
                {slot.start}-{slot.end}
                <button
                  onClick={() =>
                    setAvailableSlots(
                      availableSlots.filter(
                        (_, slotIndex) => slotIndex !== index,
                      ),
                    )
                  }
                >
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
          <form className="slot-form" onSubmit={addSlot}>
            <select
              value={slotForm.day}
              onChange={(event) =>
                setSlotForm({ ...slotForm, day: event.target.value })
              }
            >
              <option value="0">Today</option>
              <option value="1">Tomorrow</option>
              <option value="2">Day 3</option>
              <option value="3">Day 4</option>
              <option value="4">Day 5</option>
            </select>
            <input
              type="time"
              value={slotForm.start}
              onChange={(event) =>
                setSlotForm({ ...slotForm, start: event.target.value })
              }
            />
            <span>to</span>
            <input
              type="time"
              value={slotForm.end}
              onChange={(event) =>
                setSlotForm({ ...slotForm, end: event.target.value })
              }
            />
            <button className="add-slot-button" title="Add time slot">
              <Plus size={15} />
            </button>
          </form>
        </section>

        <section className="panel plan-panel">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">02 / OUTPUT</p>
              <h2>Study rhythm</h2>
            </div>
            <button
              className="generate-button"
              onClick={generateSchedule}
              disabled={loading}
            >
              {loading ? (
                "Thinking..."
              ) : (
                <>
                  <RefreshCw size={15} /> Recalculate
                </>
              )}
            </button>
          </div>
          {error && <div className="error-banner">{error}</div>}
          <div className="priority-strip">
            <div>
              <span className="mini-label">Priority order</span>
              <div className="priority-list">
                {schedule?.priority_order.map((subject, index) => (
                  <span key={subject}>
                    <b>{String(index + 1).padStart(2, "0")}</b>
                    {subject}
                  </span>
                ))}
              </div>
            </div>
            <div className="ai-badge">
              <Sparkles size={14} /> Adaptive
            </div>
          </div>
          <div className="timetable-toolbar">
            <div className="view-switch">
              <button
                className={view === "today" ? "active" : ""}
                onClick={() => setView("today")}
              >
                Today
              </button>
              <button
                className={view === "week" ? "active" : ""}
                onClick={() => setView("week")}
              >
                Weekly timetable
              </button>
            </div>
            <span className="clock-note">
              Device time ·{" "}
              {clock.toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          </div>
          <div className="timetable">
            {Object.keys(groupedSchedule).length ? (
              Object.entries(groupedSchedule).map(([day, items]) => (
                <div className="day-column" key={day}>
                  <div className="day-label">
                    {Number(day) === 0 ? "TODAY" : `DAY ${Number(day) + 1}`}
                    <span>{items.length} slots</span>
                  </div>
                  {items.map((item) => (
                    <div
                      className={`schedule-block ${item.difficulty.toLowerCase()}`}
                      key={`${day}-${item.start}-${item.end}-${item.subject}`}
                    >
                      <div>
                        <strong>
                          {item.time}: {item.subject}
                        </strong>
                        <span>
                          {item.difficulty} · priority {item.priority}
                        </span>
                      </div>
                      <select
                        className={`block-status ${item.status.toLowerCase().replace(" ", "-")}`}
                        value={item.status}
                        onChange={(event) =>
                          updateScheduleStatus(item, event.target.value)
                        }
                      >
                        <option>Planned</option>
                        <option>In progress</option>
                        <option>Completed</option>
                        <option>Missed</option>
                      </select>
                    </div>
                  ))}
                </div>
              ))
            ) : (
              <div className="empty-state">
                Add a task to generate your study rhythm.
              </div>
            )}
          </div>
        </section>
      </div>
      <footer>
        <span>“Constraint-based scheduling with heuristic optimization.”</span>
        <span>
          FocusFlow prototype <span className="divider" /> v1.0
        </span>
      </footer>
    </main>
  );
}

function Stat({ icon, label, value, note, accent }) {
  return (
    <div className={`stat-card ${accent ? "accent" : ""}`}>
      <div className="stat-icon">{icon}</div>
      <span className="stat-label">{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </div>
  );
}
function TaskRow({ task, onDelete, onStatus }) {
  return (
    <div className="task-row">
      <div className={`task-dot ${task.difficulty.toLowerCase()}`} />
      <div className="task-info">
        <strong>{task.subject}</strong>
        <span>
          {task.difficulty} · due in {task.deadline_days} days
        </span>
      </div>
      <select
        className={`status-select ${task.status.toLowerCase().replace(" ", "-")}`}
        value={task.status}
        onChange={(event) => onStatus(event.target.value)}
        aria-label={`Status for ${task.subject}`}
      >
        <option>Planned</option>
        <option>In progress</option>
        <option>Missed</option>
        <option>Completed</option>
      </select>
      <button
        className="delete-button"
        onClick={onDelete}
        title={`Remove ${task.subject}`}
      >
        <Trash2 size={15} />
      </button>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
