import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Brain,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  Clock,
  Compass,
  FileText,
  Flame,
  HelpCircle,
  Layers,
  LineChart,
  Play,
  PlusCircle,
  RefreshCw,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Upload,
  XCircle,
} from "lucide-react";
import "./styles.css";

const API_BASE = "http://localhost:8000/api";

function App() {
  const [activeTab, setActiveTab] = useState("plan"); // "plan" | "quiz" | "curve" | "materials" | "dashboard"
  const [dashboard, setDashboard] = useState(null);
  const [todayPlan, setTodayPlan] = useState(null);
  const [concepts, setConcepts] = useState([]);
  const [selectedConceptId, setSelectedConceptId] = useState(1);
  const [curveData, setCurveData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");

  // Quiz state
  const [activeQuiz, setActiveQuiz] = useState(null);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [selectedOption, setSelectedOption] = useState(null);
  const [answerFeedback, setAnswerFeedback] = useState(null);
  const [sessionCompletedSummary, setSessionCompletedSummary] = useState(null);

  // Material upload state
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadContent, setUploadContent] = useState("");
  const [uploading, setUploading] = useState(false);

  // Initial data loading
  useEffect(() => {
    fetchDashboard();
    fetchPlan();
    fetchConcepts();
  }, []);

  useEffect(() => {
    if (selectedConceptId) {
      fetchCurve(selectedConceptId);
    }
  }, [selectedConceptId]);

  const fetchDashboard = async () => {
    try {
      const res = await fetch(`${API_BASE}/dashboard?user_id=1`);
      if (res.ok) setDashboard(await res.json());
    } catch (e) {
      console.warn("Using offline fallback for dashboard", e);
    }
  };

  const fetchPlan = async () => {
    try {
      const res = await fetch(`${API_BASE}/plan/today?user_id=1`);
      if (res.ok) setTodayPlan(await res.json());
    } catch (e) {
      console.warn("Using offline fallback for plan", e);
    }
  };

  const fetchConcepts = async () => {
    try {
      const res = await fetch(`${API_BASE}/concepts?user_id=1`);
      if (res.ok) {
        const data = await res.json();
        setConcepts(data);
        if (data.length > 0 && !selectedConceptId) {
          setSelectedConceptId(data[0].id);
        }
      }
    } catch (e) {
      console.warn("Using offline fallback for concepts", e);
    }
  };

  const fetchCurve = async (id) => {
    try {
      const res = await fetch(`${API_BASE}/concepts/${id}/curve?user_id=1`);
      if (res.ok) setCurveData(await res.json());
    } catch (e) {
      console.warn("Error fetching curve", e);
    }
  };

  const startQuizSession = async (conceptId = null) => {
    setLoading(true);
    setSessionCompletedSummary(null);
    setCurrentQuestionIndex(0);
    setSelectedOption(null);
    setAnswerFeedback(null);
    try {
      const body = { user_id: 1, limit: 5 };
      if (conceptId) body.concept_ids = [conceptId];
      const res = await fetch(`${API_BASE}/quizzes/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const data = await res.json();
        setActiveQuiz(data);
        setActiveTab("quiz");
      }
    } catch (e) {
      alert("Could not start quiz: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectOption = async (optionIndex) => {
    if (selectedOption !== null || !activeQuiz) return;
    setSelectedOption(optionIndex);

    const question = activeQuiz.questions[currentQuestionIndex];
    const eventId = `evt-${activeQuiz.session_id}-${question.question_id}-${Date.now()}`;

    try {
      const res = await fetch(`${API_BASE}/sessions/${activeQuiz.session_id}/answers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event_id: eventId,
          question_id: question.question_id,
          selected_index: optionIndex,
        }),
      });
      if (res.ok) {
        const result = await res.json();
        setAnswerFeedback(result);
      }
    } catch (e) {
      console.error("Failed to submit answer", e);
    }
  };

  const handleNextQuestion = () => {
    setSelectedOption(null);
    setAnswerFeedback(null);
    if (currentQuestionIndex + 1 < (activeQuiz?.questions?.length || 0)) {
      setCurrentQuestionIndex((prev) => prev + 1);
    } else {
      handleCompleteSession();
    }
  };

  const handleCompleteSession = async () => {
    if (!activeQuiz) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/sessions/${activeQuiz.session_id}/complete`, {
        method: "POST",
      });
      if (res.ok) {
        const summary = await res.json();
        setSessionCompletedSummary(summary);
        // Refresh data
        fetchDashboard();
        fetchPlan();
        fetchConcepts();
        if (selectedConceptId) fetchCurve(selectedConceptId);
      }
    } catch (e) {
      alert("Failed to complete session: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleUploadMaterial = async (e) => {
    e.preventDefault();
    if (!uploadTitle.trim() || !uploadContent.trim()) return;
    setUploading(true);
    try {
      const res = await fetch(`${API_BASE}/materials`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          subject_id: 1,
          title: uploadTitle,
          content: uploadContent,
        }),
      });
      if (res.ok) {
        const result = await res.json();
        setStatusMessage(`Generated ${result.concepts_generated} concepts and ${result.questions_generated} quiz questions!`);
        setUploadTitle("");
        setUploadContent("");
        fetchConcepts();
        fetchDashboard();
        fetchPlan();
      }
    } catch (err) {
      alert("Upload failed: " + err.message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="app-shell">
      {/* Top Navbar */}
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            <Brain size={18} />
          </div>
          <div>
            <span style={{ fontWeight: 800 }}>FocusFlow</span>
            <span style={{ marginLeft: 8, fontSize: 12, padding: "2px 8px", background: "#e0e7ff", color: "#3730a3", borderRadius: 12, fontWeight: 700 }}>
              HLR Engine
            </span>
          </div>
        </div>

        <nav className="nav-tabs">
          <button
            className={`nav-tab-btn ${activeTab === "plan" ? "active" : ""}`}
            onClick={() => setActiveTab("plan")}
          >
            <CalendarDays size={16} /> Today's Plan
          </button>
          <button
            className={`nav-tab-btn ${activeTab === "curve" ? "active" : ""}`}
            onClick={() => setActiveTab("curve")}
          >
            <LineChart size={16} /> Forgetting Curve
          </button>
          <button
            className={`nav-tab-btn ${activeTab === "quiz" ? "active" : ""}`}
            onClick={() => {
              if (!activeQuiz) startQuizSession();
              else setActiveTab("quiz");
            }}
          >
            <Play size={16} /> Practice Quiz
          </button>
          <button
            className={`nav-tab-btn ${activeTab === "materials" ? "active" : ""}`}
            onClick={() => setActiveTab("materials")}
          >
            <Upload size={16} /> Add Notes
          </button>
          <button
            className={`nav-tab-btn ${activeTab === "dashboard" ? "active" : ""}`}
            onClick={() => setActiveTab("dashboard")}
          >
            <Layers size={16} /> Retention Stats
          </button>
        </nav>
      </header>

      {/* Model Spec Badge */}
      <div className="hlr-engine-banner">
        <div className="hlr-badge">
          <Sparkles size={14} /> Active Model: <strong>v1.0 Launch (Leitner Counts)</strong>
        </div>
        <div className="hlr-meta">
          <span>Target Retention: <strong>70%</strong></span>
          <span>•</span>
          <span>Weights: <strong>Θ = [1.0, 1.0, -1.0]</strong></span>
          <span>•</span>
          <span>Bounds: <strong>[15m, 270d]</strong></span>
        </div>
      </div>

      {/* TAB 1: TODAY'S STUDY PLAN */}
      {activeTab === "plan" && (
        <section className="tab-content">
          <div className="section-head">
            <div>
              <h2>Today's Adaptive Study Plan</h2>
              <p className="subtitle">
                Study slots prioritized by Duolingo's Half-Life Regression model. Concepts with lowest recall probability are scheduled first.
              </p>
            </div>
            <button className="primary-action-btn" onClick={() => startQuizSession()}>
              <Play size={16} /> Start Full Session (15m)
            </button>
          </div>

          <div className="metrics-row">
            <div className="metric-box">
              <span className="metric-label">Allocated Daily Time</span>
              <span className="metric-value">{todayPlan?.plan?.[0]?.total_minutes || 60}m</span>
              <span className="metric-sub">Budget: {todayPlan?.daily_budget_minutes || 60}m</span>
            </div>
            <div className="metric-box">
              <span className="metric-label">Concepts Due Today</span>
              <span className="metric-value">{todayPlan?.plan?.[0]?.concepts?.length || 0}</span>
              <span className="metric-sub">Sorted by lowest retention</span>
            </div>
            <div className="metric-box">
              <span className="metric-label">Overall Retention Rate</span>
              <span className="metric-value">{dashboard ? Math.round(dashboard.overall_retention * 100) : 75}%</span>
              <span className="metric-sub">Target: ≥ 70%</span>
            </div>
          </div>

          <div className="concepts-grid">
            {todayPlan?.plan?.[0]?.concepts?.map((c) => (
              <div key={c.concept_id} className="concept-card">
                <div className="concept-card-top">
                  <span className="subject-pill" style={{ borderColor: c.subject_color, color: c.subject_color }}>
                    {c.subject_name}
                  </span>
                  <span className={`status-pill ${c.due_status}`}>
                    {c.due_status.toUpperCase()}
                  </span>
                </div>
                <h3 className="concept-name">{c.concept_name}</h3>
                
                <div className="concept-stats">
                  <div>
                    <div className="stat-sub">Estimated Recall (p̂)</div>
                    <div className="stat-main" style={{ color: c.current_p < 0.6 ? "#dc2626" : "#16a34a" }}>
                      {Math.round(c.current_p * 100)}%
                    </div>
                  </div>
                  <div>
                    <div className="stat-sub">Memory Half-Life (ĥ)</div>
                    <div className="stat-main">{c.h_hat} days</div>
                  </div>
                  <div>
                    <div className="stat-sub">Allocated Slot</div>
                    <div className="stat-main">{c.allocated_minutes} mins</div>
                  </div>
                </div>

                <div className="concept-card-actions">
                  <button
                    className="small-btn outline"
                    onClick={() => {
                      setSelectedConceptId(c.concept_id);
                      setActiveTab("curve");
                    }}
                  >
                    <LineChart size={14} /> View Decay Curve
                  </button>
                  <button
                    className="small-btn primary"
                    onClick={() => startQuizSession(c.concept_id)}
                  >
                    <Play size={14} /> Practice Now
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* TAB 2: ACTIVE QUIZ */}
      {activeTab === "quiz" && (
        <section className="tab-content quiz-section">
          {sessionCompletedSummary ? (
            <div className="session-summary-card">
              <div className="summary-icon">
                <CheckCircle2 size={48} color="#16a34a" />
              </div>
              <h2>Session Complete!</h2>
              <p className="subtitle">
                HLR memory state updated. Training records logged to database for online and offline evaluation.
              </p>

              <div className="summary-score">
                Accuracy: <strong>{Math.round(sessionCompletedSummary.session_accuracy * 100)}%</strong> ({sessionCompletedSummary.total_correct}/{sessionCompletedSummary.total_attempts} correct)
              </div>

              <h3>Updated Memory Half-Lives</h3>
              <div className="summary-list">
                {sessionCompletedSummary.concepts_updated.map((cu) => (
                  <div key={cu.concept_id} className="summary-item">
                    <div>
                      <strong>Concept #{cu.concept_id}</strong>
                      <div className="stat-sub">Session Recall: {Math.round(cu.p_observed * 100)}% ({cu.session_correct}/{cu.session_total})</div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div className="stat-main" style={{ color: "#4f46e5" }}>
                        New ĥ: {cu.new_h_hat} days
                      </div>
                      <div className="stat-sub">Next review: {new Date(cu.next_review_at).toLocaleDateString()}</div>
                    </div>
                  </div>
                ))}
              </div>

              <div style={{ marginTop: 24, display: "flex", gap: 12 }}>
                <button className="primary-action-btn" onClick={() => startQuizSession()}>
                  Start Another Quiz
                </button>
                <button className="small-btn outline" onClick={() => setActiveTab("curve")}>
                  Inspect Forgetting Curves
                </button>
              </div>
            </div>
          ) : activeQuiz && activeQuiz.questions?.length > 0 ? (
            <div className="quiz-card">
              <div className="quiz-progress-bar">
                <div
                  className="quiz-progress-fill"
                  style={{ width: `${((currentQuestionIndex + 1) / activeQuiz.questions.length) * 100}%` }}
                />
              </div>

              <div className="quiz-header">
                <span className="concept-tag">{activeQuiz.questions[currentQuestionIndex].concept_name}</span>
                <span className="quiz-counter">
                  Question {currentQuestionIndex + 1} of {activeQuiz.questions.length}
                </span>
              </div>

              <h2 className="quiz-question-text">
                {activeQuiz.questions[currentQuestionIndex].text}
              </h2>

              <div className="quiz-options-list">
                {activeQuiz.questions[currentQuestionIndex].options.map((opt, idx) => {
                  let optClass = "quiz-option-btn";
                  if (selectedOption !== null) {
                    if (idx === answerFeedback?.correct_index) optClass += " correct";
                    else if (idx === selectedOption) optClass += " wrong";
                    else optClass += " disabled";
                  }
                  return (
                    <button
                      key={idx}
                      className={optClass}
                      disabled={selectedOption !== null}
                      onClick={() => handleSelectOption(idx)}
                    >
                      <span className="option-letter">{String.fromCharCode(65 + idx)}</span>
                      <span className="option-text">{opt}</span>
                    </button>
                  );
                })}
              </div>

              {answerFeedback && (
                <div className={`answer-feedback-box ${answerFeedback.is_correct ? "correct" : "wrong"}`}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 700 }}>
                    {answerFeedback.is_correct ? (
                      <>
                        <CheckCircle2 size={18} color="#16a34a" /> Correct! Half-life will lengthen.
                      </>
                    ) : (
                      <>
                        <XCircle size={18} color="#dc2626" /> Incorrect. Memory decay will shorten.
                      </>
                    )}
                  </div>
                  {answerFeedback.explanation && (
                    <p style={{ margin: "6px 0 0 0", fontSize: 13, color: "#374151" }}>
                      {answerFeedback.explanation}
                    </p>
                  )}
                </div>
              )}

              {selectedOption !== null && (
                <div className="quiz-footer">
                  <button className="primary-action-btn" onClick={handleNextQuestion}>
                    {currentQuestionIndex + 1 < activeQuiz.questions.length ? "Next Question" : "Complete Session"}
                    <ChevronRight size={16} />
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="empty-state-box">
              <HelpCircle size={40} color="#9ca3af" />
              <h3>No Active Quiz Session</h3>
              <p>Start a quiz to review concepts and train your memory half-life model.</p>
              <button className="primary-action-btn" onClick={() => startQuizSession()}>
                <Play size={16} /> Start Quiz Session
              </button>
            </div>
          )}
        </section>
      )}

      {/* TAB 3: FORGETTING CURVE (PAPER FIG 4) */}
      {activeTab === "curve" && (
        <section className="tab-content">
          <div className="section-head">
            <div>
              <h2>Exponential Forgetting Curve</h2>
              <p className="subtitle">
                Duolingo Half-Life Regression: p̂(t) = 2^(-Δ / ĥ). When recall drops below 70%, a review is scheduled.
              </p>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <label style={{ fontSize: 13, fontWeight: 600 }}>Select Concept:</label>
              <select
                className="select-input"
                value={selectedConceptId}
                onChange={(e) => setSelectedConceptId(Number(e.target.value))}
              >
                {concepts.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} (ĥ = {c.h_hat}d)
                  </option>
                ))}
              </select>
            </div>
          </div>

          {curveData ? (
            <div className="curve-layout">
              <div className="curve-chart-card">
                <div className="chart-legend">
                  <span className="legend-item"><span className="legend-color-line" /> Predicted Retention Curve p̂(t)</span>
                  <span className="legend-item"><span className="legend-color-thresh" /> Target Review Threshold (70%)</span>
                </div>

                {/* SVG Forgetting Curve Chart */}
                <div className="svg-chart-container">
                  <svg viewBox="0 0 700 320" className="forgetting-curve-svg">
                    {/* Grid lines */}
                    <line x1="60" y1="30" x2="680" y2="30" stroke="#f1f5f9" strokeWidth="1" />
                    <line x1="60" y1="95" x2="680" y2="95" stroke="#f1f5f9" strokeWidth="1" />
                    <line x1="60" y1="160" x2="680" y2="160" stroke="#f1f5f9" strokeWidth="1" />
                    <line x1="60" y1="225" x2="680" y2="225" stroke="#f1f5f9" strokeWidth="1" />
                    <line x1="60" y1="270" x2="680" y2="270" stroke="#cbd5e1" strokeWidth="1.5" />
                    <line x1="60" y1="30" x2="60" y2="270" stroke="#cbd5e1" strokeWidth="1.5" />

                    {/* Y-axis labels */}
                    <text x="25" y="35" className="axis-text">100%</text>
                    <text x="30" y="100" className="axis-text">75%</text>
                    <text x="30" y="165" className="axis-text">50%</text>
                    <text x="30" y="230" className="axis-text">25%</text>
                    <text x="35" y="275" className="axis-text">0%</text>

                    {/* 70% Threshold Line */}
                    {/* y for 70% is 270 - (0.7 * 240) = 270 - 168 = 102 */}
                    <line x1="60" y1="102" x2="680" y2="102" stroke="#ef4444" strokeWidth="1.5" strokeDasharray="5,4" />
                    <text x="610" y="96" fill="#ef4444" fontSize="11" fontWeight="700">70% Threshold</text>

                    {/* Decay Curve Path */}
                    {(() => {
                      const pts = curveData.curve_points;
                      if (!pts || pts.length === 0) return null;
                      const maxD = pts[pts.length - 1].day || 10;
                      const pathCoords = pts.map((pt, i) => {
                        const x = 60 + (pt.day / maxD) * 600;
                        const y = 270 - pt.probability * 240;
                        return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
                      });
                      return (
                        <path
                          d={pathCoords.join(" ")}
                          fill="none"
                          stroke="#4f46e5"
                          strokeWidth="3"
                          strokeLinecap="round"
                        />
                      );
                    })()}

                    {/* Current Delta point */}
                    {(() => {
                      const pts = curveData.curve_points;
                      const maxD = pts?.[pts.length - 1]?.day || 10;
                      const curX = 60 + (Math.min(curveData.current_delta_days, maxD) / maxD) * 600;
                      const curY = 270 - curveData.current_p * 240;
                      return (
                        <g>
                          <circle cx={curX} cy={curY} r="7" fill="#4f46e5" stroke="#ffffff" strokeWidth="2.5" />
                          <text x={curX + 10} y={curY - 10} fill="#1e1b4b" fontSize="12" fontWeight="700">
                            Now ({Math.round(curveData.current_p * 100)}%)
                          </text>
                        </g>
                      );
                    })()}

                    {/* X-axis labels */}
                    <text x="60" y="295" className="axis-text">Day 0</text>
                    <text x="350" y="295" className="axis-text">
                      Elapsed Days (Δ) →
                    </text>
                    <text x="640" y="295" className="axis-text">
                      {curveData.curve_points[curveData.curve_points.length - 1]?.day}d
                    </text>
                  </svg>
                </div>
              </div>

              <div className="curve-info-panel">
                <div className="info-card">
                  <h4>Memory Half-Life (ĥ)</h4>
                  <div className="info-val">{curveData.h_hat} days</div>
                  <p className="info-desc">
                    Time required for memory strength to drop to exactly 50%.
                  </p>
                </div>

                <div className="info-card">
                  <h4>Current Retention (p̂)</h4>
                  <div className="info-val" style={{ color: curveData.current_p < 0.7 ? "#dc2626" : "#16a34a" }}>
                    {Math.round(curveData.current_p * 100)}%
                  </div>
                  <p className="info-desc">
                    {curveData.current_delta_days} days since last review.
                  </p>
                </div>

                <div className="info-card">
                  <h4>Next Review Recommended</h4>
                  <div className="info-val">In {curveData.next_review_days} days</div>
                  <p className="info-desc">
                    Calculated as -ĥ · log₂(0.7) ≈ 0.514 · ĥ.
                  </p>
                </div>

                <button
                  className="primary-action-btn"
                  style={{ width: "100%", marginTop: 8 }}
                  onClick={() => startQuizSession(curveData.concept_id)}
                >
                  <Play size={16} /> Practice This Concept
                </button>
              </div>
            </div>
          ) : (
            <div className="empty-state-box">Select a concept to view its forgetting curve.</div>
          )}
        </section>
      )}

      {/* TAB 4: MATERIALS UPLOAD */}
      {activeTab === "materials" && (
        <section className="tab-content">
          <div className="section-head">
            <div>
              <h2>Upload Study Notes & Generate Quizzes</h2>
              <p className="subtitle">
                Paste notes, textbook chapters, or lecture slides. The engine extracts concepts, tags them, and creates quiz questions.
              </p>
            </div>
          </div>

          {statusMessage && (
            <div className="status-message-banner">
              <CheckCircle2 size={16} /> {statusMessage}
            </div>
          )}

          <form className="materials-form" onSubmit={handleUploadMaterial}>
            <div className="form-group">
              <label>Topic / Material Title</label>
              <input
                className="text-input"
                placeholder="e.g. Distributed Consensus & Raft Protocol"
                value={uploadTitle}
                onChange={(e) => setUploadTitle(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label>Notes / Content</label>
              <textarea
                className="textarea-input"
                rows={8}
                placeholder="Paste key notes, bullet points, definitions, or exam material here..."
                value={uploadContent}
                onChange={(e) => setUploadContent(e.target.value)}
                required
              />
            </div>

            <button type="submit" className="primary-action-btn" disabled={uploading}>
              {uploading ? <RefreshCw size={16} className="spin" /> : <Sparkles size={16} />}
              {uploading ? "Extracting Concepts & Generating..." : "Generate Concepts & Questions"}
            </button>
          </form>

          <h3 style={{ marginTop: 36 }}>Current Concept Library ({concepts.length})</h3>
          <div className="concepts-compact-list">
            {concepts.map((c) => (
              <div key={c.id} className="concept-compact-row">
                <div>
                  <strong>{c.name}</strong>
                  <div className="stat-sub">{c.description || "Core subject concept"}</div>
                </div>
                <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                  <span className="stat-sub">ĥ = {c.h_hat}d</span>
                  <span className="stat-sub">Recall: {Math.round(c.p_hat_current * 100)}%</span>
                  <button
                    className="small-btn outline"
                    onClick={() => {
                      setSelectedConceptId(c.id);
                      setActiveTab("curve");
                    }}
                  >
                    Curve
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* TAB 5: RETENTION DASHBOARD */}
      {activeTab === "dashboard" && (
        <section className="tab-content">
          <div className="section-head">
            <div>
              <h2>Memory Retention Dashboard</h2>
              <p className="subtitle">
                Subject-level memory aggregation and HLR model status.
              </p>
            </div>
          </div>

          <div className="metrics-row">
            <div className="metric-box">
              <span className="metric-label">Average Retention</span>
              <span className="metric-value">{dashboard ? Math.round(dashboard.overall_retention * 100) : 75}%</span>
              <span className="metric-sub">Duolingo HLR Target: 70%</span>
            </div>
            <div className="metric-box">
              <span className="metric-label">Concepts Due for Review</span>
              <span className="metric-value">{dashboard?.total_due_concepts || 0}</span>
              <span className="metric-sub">Recall probability &lt; 70%</span>
            </div>
            <div className="metric-box">
              <span className="metric-label">Active Subjects</span>
              <span className="metric-value">{dashboard?.subjects?.length || 0}</span>
              <span className="metric-sub">Multi-disciplinary planning</span>
            </div>
          </div>

          <h3 style={{ marginTop: 24 }}>Subject Memory Strength</h3>
          <div className="subject-cards-grid">
            {dashboard?.subjects?.map((s) => (
              <div key={s.subject_id} className="subject-card">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <h4 style={{ margin: 0, color: s.color }}>{s.name}</h4>
                  <span className="concept-count-tag">{s.total_concepts} concepts</span>
                </div>

                <div className="progress-container">
                  <div className="progress-label">
                    <span>Average Memory Retention</span>
                    <strong>{Math.round(s.avg_p_hat * 100)}%</strong>
                  </div>
                  <div className="progress-bar-bg">
                    <div
                      className="progress-bar-fill"
                      style={{
                        width: `${Math.round(s.avg_p_hat * 100)}%`,
                        backgroundColor: s.avg_p_hat < 0.6 ? "#ef4444" : s.color,
                      }}
                    />
                  </div>
                </div>

                <div className="subject-footer-stats">
                  <span><strong>{s.due_concepts_count}</strong> Due for Review</span>
                  <span><strong>{s.weak_concepts_count}</strong> Critical (&lt;60%)</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

const root = createRoot(document.getElementById("root"));
root.render(<App />);
