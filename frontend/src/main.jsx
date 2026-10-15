import React, { useState, useEffect, useMemo } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Brain,
  BookOpen,
  Calendar,
  CheckCircle2,
  Clock,
  Compass,
  FileText,
  Flame,
  Layers,
  LineChart,
  Play,
  RotateCcw,
  Settings,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Upload,
  AlertTriangle,
  ArrowRight,
  Check,
  X,
  Flag,
  HelpCircle,
  Sliders,
  Award,
  Zap,
  ChevronRight,
  Database,
  MessageSquare,
  Bot,
  Send,
  Lightbulb,
  Copy,
  CheckCheck,
  RefreshCw
} from 'lucide-react';
import './styles.css';

const API_BASE = 'http://localhost:8000/api';

// ---------------------------------------------------------------------------
// HLR Math Helper (Duolingo: Settles & Meeder, 2016)
// ---------------------------------------------------------------------------
import {
  H_MIN,
  H_MAX,
  P_MIN,
  P_MAX,
  LAUNCH_THETA,
  calcHalfLife,
  calcRecallProb,
  calcNextReviewDays
} from './hlr.js';

// ---------------------------------------------------------------------------
// Seed Data
// ---------------------------------------------------------------------------
const SEED_CONCEPTS = [
  { id: 'c-ai-1', subject: 'Artificial Intelligence', topic: 'Neural Networks', name: 'Backpropagation & Chain Rule', difficulty: 'Hard', n_right: 3, n_wrong: 1, days_ago: 2.5 },
  { id: 'c-ai-2', subject: 'Artificial Intelligence', topic: 'Transformers', name: 'Scaled Dot-Product Attention', difficulty: 'Hard', n_right: 4, n_wrong: 0, days_ago: 1.8 },
  { id: 'c-ai-3', subject: 'Artificial Intelligence', topic: 'Search Algorithms', name: 'A* Heuristic Admissibility', difficulty: 'Medium', n_right: 1, n_wrong: 2, days_ago: 4.1 },
  { id: 'c-os-1', subject: 'Operating Systems', topic: 'Virtual Memory', name: 'Page Replacement (LRU vs Clock)', difficulty: 'Medium', n_right: 2, n_wrong: 2, days_ago: 3.2 },
  { id: 'c-os-2', subject: 'Operating Systems', topic: 'Concurrency', name: 'Deadlock Coffman Conditions', difficulty: 'Hard', n_right: 5, n_wrong: 1, days_ago: 6.0 },
  { id: 'c-math-1', subject: 'Mathematics', topic: 'Linear Algebra', name: 'Eigenvalues and Eigendecomposition', difficulty: 'Hard', n_right: 2, n_wrong: 3, days_ago: 3.8 },
  { id: 'c-math-2', subject: 'Mathematics', topic: 'Probability', name: "Bayes' Theorem & Posterior Update", difficulty: 'Medium', n_right: 4, n_wrong: 1, days_ago: 0.8 },
  { id: 'c-ds-1', subject: 'Distributed Systems', topic: 'Consensus', name: 'Raft Leader Election & Term Logic', difficulty: 'Hard', n_right: 1, n_wrong: 3, days_ago: 5.0 },
  { id: 'c-ds-2', subject: 'Distributed Systems', topic: 'Consistency', name: 'CAP Theorem & PACELC Tradeoffs', difficulty: 'Medium', n_right: 3, n_wrong: 0, days_ago: 1.2 }
];

const SEED_QUESTIONS = [
  {
    id: 'q-1',
    concept_id: 'c-ai-1',
    concept_name: 'Backpropagation & Chain Rule',
    subject: 'Artificial Intelligence',
    text: 'In backward propagation of errors, how is the gradient of the loss with respect to a weight W calculated when computing layer gradients?',
    options: [
      'By recursively multiplying the upstream gradient with the local derivative of the activation and previous activation',
      'By taking the direct second derivative of the loss function with respect to input features',
      'By calculating the inverse Jacobian matrix of the output layer only',
      'By subtracting the learning rate multiplied by previous momentum'
    ],
    answer_index: 0,
    explanation: 'Backpropagation utilizes the multivariate chain rule: upstream gradient dL/dz is multiplied by the local gradient dz/dW (which is the input activation) to compute dL/dW.',
    status: 'approved'
  },
  {
    id: 'q-2',
    concept_id: 'c-ai-2',
    concept_name: 'Scaled Dot-Product Attention',
    subject: 'Artificial Intelligence',
    text: 'Why do standard Transformer architectures divide the query-key dot product by sqrt(d_k)?',
    options: [
      'To prevent the dot products from growing excessively large, which pushes softmax into saturated regions with tiny gradients',
      'To ensure the resulting attention weights sum up to exactly sqrt(d_k)',
      'To enforce orthogonality between Query and Key projection matrices',
      'To convert quadratic computational complexity O(n^2) into linear complexity'
    ],
    answer_index: 0,
    explanation: 'As d_k increases, the variance of the dot products grows, pushing softmax into saturated regimes with vanishingly small gradients. Scaling by 1/sqrt(d_k) preserves unit variance.',
    status: 'approved'
  },
  {
    id: 'q-3',
    concept_id: 'c-ai-3',
    concept_name: 'A* Heuristic Admissibility',
    subject: 'Artificial Intelligence',
    text: "What condition defines an 'admissible' heuristic h(n) in the A* graph search algorithm?",
    options: [
      'h(n) never overestimates the actual minimal cost to reach the goal from node n',
      'h(n) must equal exactly the Euclidean distance in all coordinate spaces',
      'h(n) must be strictly monotonic and greater than the path cost g(n)',
      'h(n) must be computed in constant time O(1) without accessing neighboring edges'
    ],
    answer_index: 0,
    explanation: 'An admissible heuristic never overestimates the true remaining cost to the goal (h(n) <= h*(n)), guaranteeing that A* tree search finds an optimal solution.',
    status: 'approved'
  },
  {
    id: 'q-4',
    concept_id: 'c-os-1',
    concept_name: 'Page Replacement (LRU vs Clock)',
    subject: 'Operating Systems',
    text: 'How does the Clock (Second-Chance) page replacement algorithm approximate true Least Recently Used (LRU) paging?',
    options: [
      'It inspects a reference bit for each page, resetting it to 0 if 1 and advancing the pointer until it finds a page with 0',
      'It maintains an exact doubly linked list ordered by precise CPU timestamp on every memory access',
      'It randomly evicts any page that has not been modified in the dirty register within 100 cycles',
      'It computes page fault frequency and swaps out the largest virtual memory segments first'
    ],
    answer_index: 0,
    explanation: 'The Clock algorithm rotates through pages circularly. If a page reference bit is 1, it gets a second chance (bit set to 0) and the hand advances; a page with reference bit 0 is chosen for eviction.',
    status: 'approved'
  },
  {
    id: 'q-5',
    concept_id: 'c-os-2',
    concept_name: 'Deadlock Coffman Conditions',
    subject: 'Operating Systems',
    text: 'Which of the following is NOT one of the four necessary Coffman conditions required for a deadlock to occur?',
    options: [
      'Preemptive resource allocation by the operating system scheduler',
      'Mutual Exclusion',
      'Hold and Wait',
      'Circular Wait'
    ],
    answer_index: 0,
    explanation: 'The 4 Coffman conditions are Mutual Exclusion, Hold and Wait, No Preemption, and Circular Wait. Preemption breaks deadlock!',
    status: 'approved'
  },
  {
    id: 'q-6',
    concept_id: 'c-math-1',
    concept_name: 'Eigenvalues and Eigendecomposition',
    subject: 'Mathematics',
    text: 'For a square matrix A and non-zero vector v, what characterizes v as an eigenvector corresponding to eigenvalue λ?',
    options: [
      'A * v = λ * v, meaning the transformation scales the vector without changing its direction line',
      'The determinant of A + λI must equal 1',
      'The dot product of v and λ must equal zero (orthogonal)',
      'The trace of matrix A must be equal to 1/λ'
    ],
    answer_index: 0,
    explanation: 'An eigenvector of matrix A satisfies Av = λv. Matrix multiplication acts purely as a scalar elongation or compression by factor λ along the vector span.',
    status: 'approved'
  },
  {
    id: 'q-7',
    concept_id: 'c-math-2',
    concept_name: "Bayes' Theorem & Posterior Update",
    subject: 'Mathematics',
    text: 'In Bayes formula P(H|E) = [P(E|H) * P(H)] / P(E), what does the term P(E|H) represent?',
    options: [
      'The Likelihood of observing evidence E given that hypothesis H is true',
      'The Prior probability of hypothesis H before receiving evidence',
      'The Marginal probability of the entire sample space',
      'The Posterior probability of the test evidence'
    ],
    answer_index: 0,
    explanation: 'P(E|H) is the Likelihood: the conditional probability of witnessing the observed data or symptom E given the state of nature or hypothesis H.',
    status: 'approved'
  },
  {
    id: 'q-8',
    concept_id: 'c-ds-1',
    concept_name: 'Raft Leader Election & Term Logic',
    subject: 'Distributed Systems',
    text: 'In Raft consensus, what must a Candidate node do if it receives an AppendEntries RPC from another node claiming to be Leader with a term equal to or higher than its own?',
    options: [
      'Recognize the leader as legitimate, transition back to Follower state, and reset its election timer',
      'Immediately reject the RPC and broadcast RequestVote to override the leader',
      'Increment its term number by 2 and force a network split',
      'Drop the connection and partition itself into isolation'
    ],
    answer_index: 0,
    explanation: 'If a Candidate or Follower discovers another node claiming leadership in a term greater than or equal to its own currentTerm, it steps down to Follower immediately.',
    status: 'approved'
  },
  {
    id: 'q-9',
    concept_id: 'c-ds-2',
    concept_name: 'CAP Theorem & PACELC Tradeoffs',
    subject: 'Distributed Systems',
    text: 'According to the PACELC theorem, what tradeoff must a distributed system make when there is NO network partition?',
    options: [
      'Between Latency (L) and Consistency (C)',
      'Between Availability (A) and Partition Tolerance (P)',
      'Between Security (S) and Throughput (T)',
      'Between Eventual Consistency and Total Ordering'
    ],
    answer_index: 0,
    explanation: 'PACELC states: If Partition (P), tradeoff Availability (A) and Consistency (C); Else (E), tradeoff Latency (L) and Consistency (C).',
    status: 'approved'
  }
];

function initClientConcepts() {
  return SEED_CONCEPTS.map(c => {
    const h = calcHalfLife(LAUNCH_THETA, [1.0, c.n_right, c.n_wrong]);
    const p = calcRecallProb(h, c.days_ago);
    const revDays = calcNextReviewDays(h, 0.70);
    return {
      ...c,
      half_life_days: parseFloat(h.toFixed(3)),
      p_hat: parseFloat(p.toFixed(4)),
      delta_days: c.days_ago,
      is_due: p <= 0.70,
      next_review_days: parseFloat(revDays.toFixed(1))
    };
  });
}

// ---------------------------------------------------------------------------
// Main Application Component
// ---------------------------------------------------------------------------
export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [isApiOnline, setIsApiOnline] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);

  const [concepts, setConcepts] = useState(() => initClientConcepts());
  const [questions, setQuestions] = useState(SEED_QUESTIONS);
  const [dashboardData, setDashboardData] = useState(null);
  const [todayPlan, setTodayPlan] = useState(null);
  const [selectedConceptId, setSelectedConceptId] = useState('c-ai-1');
  const [curveData, setCurveData] = useState(null);
  const [hoveredPoint, setHoveredPoint] = useState(null);

  const [settings, setSettings] = useState({
    daily_minutes: 45,
    retention_threshold: 0.70,
    subject_priorities: {
      'Artificial Intelligence': 1.4,
      'Operating Systems': 1.2,
      'Mathematics': 1.0,
      'Distributed Systems': 1.3
    },
    exam_dates: {
      'Artificial Intelligence': '2026-10-12',
      'Operating Systems': '2026-10-19',
      'Mathematics': '2026-10-28',
      'Distributed Systems': '2026-10-26'
    }
  });

  const [quizSession, setQuizSession] = useState({
    active: false,
    subjectFilter: null,
    conceptFilter: null,
    questions: [],
    currentIndex: 0,
    selectedOption: null,
    isAnswered: false,
    score: 0,
    completed: false,
    hlrFeedback: null,
    sessionResults: []
  });

  const [materialForm, setMaterialForm] = useState({
    subject: 'Artificial Intelligence',
    topic: 'Deep Learning',
    title: 'Self-Attention and Multi-Head Projections',
    content: 'Multi-head attention allows the model to jointly attend to information from different representation subspaces at different positions. It projects queries, keys, and values h times with learned linear projections.'
  });
  const [uploading, setUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [questionFilter, setQuestionFilter] = useState('all');

  const [simulatedDelta, setSimulatedDelta] = useState(2.5);

  // ---------------------------------------------------------------------------
  // AI Study Features State & Handlers
  // ---------------------------------------------------------------------------
  const [chatMessages, setChatMessages] = useState([
    {
      role: 'model',
      content: "Hello! I am your **FocusFlow Socratic Study Buddy**. I'm here to test your understanding, deconstruct challenging logic, and help you lock concepts into long-term memory. What would you like to master today?",
      timestamp: 'Just now',
      followups: [
        "Quiz me on my weakest concept",
        "Why does recall probability decay exponentially (2^-Δ/h)?",
        "Explain Raft Leader Election in 3 simple steps"
      ]
    }
  ]);
  const [chatInput, setChatInput] = useState('');
  const [chatPersona, setChatPersona] = useState('socratic');
  const [chatSubject, setChatSubject] = useState('All');
  const [chatLoading, setChatLoading] = useState(false);

  const [doubtInput, setDoubtInput] = useState('');
  const [doubtSubject, setDoubtSubject] = useState('Operating Systems');
  const [doubtConcept, setDoubtConcept] = useState('');
  const [doubtDifficulty, setDoubtDifficulty] = useState('Medium');
  const [doubtLoading, setDoubtLoading] = useState(false);
  const [doubtResult, setDoubtResult] = useState(null);
  const [selectedChallengeOption, setSelectedChallengeOption] = useState(null);

  const [mnemonicConcept, setMnemonicConcept] = useState('Raft Leader Election & Term Logic');
  const [mnemonicSubject, setMnemonicSubject] = useState('Distributed Systems');
  const [mnemonicLoading, setMnemonicLoading] = useState(false);
  const [mnemonicResult, setMnemonicResult] = useState(null);
  const [flippedCards, setFlippedCards] = useState({});
  const [copiedMnemonic, setCopiedMnemonic] = useState(false);

  async function handleSendChatMessage(textToSend = null) {
    const text = (textToSend || chatInput).trim();
    if (!text || chatLoading) return;

    const userMsg = {
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setChatMessages(prev => [...prev, userMsg]);
    setChatInput('');
    setChatLoading(true);

    try {
      if (isApiOnline) {
        const res = await fetch(`${API_BASE}/ai/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: text,
            history: chatMessages.slice(-6).map(m => ({ role: m.role, content: m.content })),
            subject: chatSubject === 'All' ? null : chatSubject,
            persona: chatPersona
          })
        });
        if (res.ok) {
          const data = await res.json();
          setChatMessages(prev => [
            ...prev,
            {
              role: 'model',
              content: data.reply,
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              followups: data.suggested_followups || [],
              aiPowered: data.ai_powered
            }
          ]);
          setChatLoading(false);
          return;
        }
      }
    } catch (e) {
      console.warn('Chat request fallback', e);
    }

    // Client-side local fallback
    setTimeout(() => {
      const fallbackReplies = {
        socratic: `That's an insightful question about **${chatSubject === 'All' ? 'your studies' : chatSubject}**! Notice how active recall strengthens memory half-life: What do you predict happens to recall probability if we wait twice as long before reviewing?`,
        exam_prep: `### Exam High-Yield Summary\n- **Key Invariant:** Under exam conditions, always identify the baseline state transition first.\n- **Duolingo HLR Principle:** Each correct review doubles estimated half-life (h), pushing the forgetting threshold further into the future.\n- **Common Trap:** Do not assume linear degradation; retention decays exponentially as 2^(-Δ/h).`,
        eli5: `Think of this like riding a bicycle: The first time you learn, you wobble. But each time you practice right before you forget, your brain builds stronger muscle memory so you can ride longer without falling!`
      };
      setChatMessages(prev => [
        ...prev,
        {
          role: 'model',
          content: fallbackReplies[chatPersona] || fallbackReplies.socratic,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          followups: [
            "Can you test me on this concept?",
            "What is a real-world software example?",
            "How does this connect to my study plan?"
          ],
          aiPowered: false
        }
      ]);
      setChatLoading(false);
    }, 600);
  }

  async function handleSolveDoubt(presetDoubt = null) {
    const text = (presetDoubt || doubtInput).trim();
    if (!text || doubtLoading) return;

    if (presetDoubt) setDoubtInput(presetDoubt);
    setDoubtLoading(true);
    setSelectedChallengeOption(null);

    try {
      if (isApiOnline) {
        const res = await fetch(`${API_BASE}/ai/solve-doubt`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            doubt: text,
            subject: doubtSubject,
            difficulty: doubtDifficulty,
            concept_context: doubtConcept || null
          })
        });
        if (res.ok) {
          const data = await res.json();
          setDoubtResult(data);
          setDoubtLoading(false);
          return;
        }
      }
    } catch (e) {
      console.warn('Doubt solver fallback', e);
    }

    // Client-side local fallback
    setTimeout(() => {
      setDoubtResult({
        doubt: text,
        subject: doubtSubject,
        core_intuition: `When dealing with "${text}", the central concept is maintaining correct state transitions across computational boundaries without incurring unbounded latency.`,
        step_by_step_solution: [
          `Identify the system constraints and initial preconditions for ${doubtSubject}.`,
          `Analyze why conventional approaches fail: state updates must preserve transactional consistency.`,
          `Apply the optimal resolution: utilize deterministic synchronization and track retention checkpoints.`
        ],
        common_pitfalls: [
          "Assuming operations complete in zero-latency without evaluating network/cache bounds.",
          "Ignoring edge conditions when concurrent updates occur simultaneously."
        ],
        retention_hook: "Core Rule: State before + verified transition = reliable post-condition.",
        verification_challenge: {
          question: `In ${doubtSubject}, what is the decisive advantage of adhering to this principle?`,
          options: [
            "Guarantees deterministic correctness across all failure modes",
            "Eliminates the need for any verification or tests",
            "Forces all operations to run sequentially on a single thread",
            "Deprecates memory management entirely"
          ],
          answer_index: 0,
          explanation: "Deterministic correctness under failure modes is the primary engineering guarantee."
        },
        ai_powered: false
      });
      setDoubtLoading(false);
    }, 700);
  }

  async function handleGenerateMnemonic(cName = null, sName = null) {
    const targetConcept = cName || mnemonicConcept;
    const targetSubject = sName || mnemonicSubject;
    if (!targetConcept || mnemonicLoading) return;

    setMnemonicLoading(true);
    setFlippedCards({});
    setCopiedMnemonic(false);

    try {
      if (isApiOnline) {
        const res = await fetch(`${API_BASE}/ai/mnemonics`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            concept_name: targetConcept,
            subject: targetSubject
          })
        });
        if (res.ok) {
          const data = await res.json();
          setMnemonicResult(data);
          setMnemonicLoading(false);
          return;
        }
      }
    } catch (e) {
      console.warn('Mnemonic fallback', e);
    }

    // Client-side local fallback
    setTimeout(() => {
      setMnemonicResult({
        concept_name: targetConcept,
        subject: targetSubject,
        story_mnemonic: `Imagine walking into a master library. At the entrance stands a clockwork automaton for "${targetConcept}". Every time a query arrives, it pulls a single lever, instantly illuminating the exact shelf so you never have to wander through dark corridors.`,
        acronym_or_rhyme: "Remember RAPID: Retrieve Actively, Prevent Invariant Decay!",
        real_world_metaphor: `Think of ${targetConcept} like an express toll tag on a highway: instead of stopping at every single toll booth, the car is identified at highway speed, keeping traffic fluid and predictable.`,
        key_takeaway: `Understanding ${targetConcept} anchors your mental framework in ${targetSubject} and preserves long-term memory half-life.`,
        flashcards: [
          {
            front: `What core invariant is established by ${targetConcept}?`,
            back: `It guarantees predictability and bounded execution time across all state transitions.`,
            hint: "Consider reliability and stability."
          },
          {
            front: `How does testing ${targetConcept} actively affect its memory half-life (h)?`,
            back: `According to the Settles & Meeder (2016) HLR model, each successful active recall doubles the half-life h.`,
            hint: "Think 2^(theta * x)."
          },
          {
            front: `What is the risk of delaying reviews for ${targetConcept}?`,
            back: `Recall probability drops exponentially (p = 2^(-Δ/h)). Once below the 0.70 threshold, mastery is lost.`,
            hint: "Ebbinghaus forgetting curve."
          }
        ],
        ai_powered: false
      });
      setMnemonicLoading(false);
    }, 700);
  }

  // ---------------------------------------------------------------------------
  // Data Fetching & Sync
  // ---------------------------------------------------------------------------
  async function checkBackendAndLoad() {
    try {
      const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(1500) });
      if (res.ok) {
        setIsApiOnline(true);
        loadDashboard();
        loadConcepts();
        loadTodayPlan();
      } else {
        setIsApiOnline(false);
      }
    } catch {
      setIsApiOnline(false);
    }
  }

  async function loadDashboard() {
    try {
      const res = await fetch(`${API_BASE}/dashboard`);
      if (res.ok) {
        const data = await res.json();
        setDashboardData(data);
      }
    } catch (e) {
      console.warn('Backend unavailable, using client state', e);
    }
  }

  async function loadConcepts() {
    try {
      const res = await fetch(`${API_BASE}/concepts`);
      if (res.ok) {
        const data = await res.json();
        setConcepts(data);
      }
    } catch (e) {
      console.warn(e);
    }
  }

  async function loadTodayPlan() {
    try {
      const res = await fetch(`${API_BASE}/plan/today`);
      if (res.ok) {
        const data = await res.json();
        setTodayPlan(data);
      }
    } catch (e) {
      console.warn(e);
    }
  }

  async function loadConceptCurve(cId) {
    try {
      const res = await fetch(`${API_BASE}/concepts/${cId}/curve`);
      if (res.ok) {
        const data = await res.json();
        setCurveData(data);
        setSimulatedDelta(data.current_delta_days || 2.0);
        return;
      }
    } catch (e) {
      console.warn(e);
    }

    const targetC = concepts.find(c => c.id === cId) || concepts[0];
    const h = targetC.half_life_days;
    const maxDays = Math.max(8.0, h * 2.5);
    const step = maxDays / 34;
    const points = [];
    for (let i = 0; i <= 34; i++) {
      const d = parseFloat((i * step).toFixed(2));
      const p = calcRecallProb(h, d);
      points.push({ delta_days: d, p_hat: p, retention_pct: Math.round(p * 100), threshold: 70 });
    }
    setCurveData({
      concept: targetC,
      half_life_days: h,
      current_delta_days: targetC.delta_days,
      current_p_hat: targetC.p_hat,
      threshold: settings.retention_threshold,
      curve_points: points,
      practice_points: [
        { delta_days: 0.0, p_observed: 1.0, type: 'Initial Study', date: '5d ago' },
        { delta_days: parseFloat((targetC.delta_days * 0.5).toFixed(1)), p_observed: 0.85, type: 'Quiz #1', date: '3d ago' },
        { delta_days: targetC.delta_days, p_observed: targetC.p_hat, type: 'Last Review', date: 'Today' }
      ],
      model_spec: {
        theta: LAUNCH_THETA,
        x: [1.0, targetC.n_right, targetC.n_wrong],
        formula: 'h = 2^(θ0 + θ_right * n_right + θ_wrong * n_wrong)'
      }
    });
    setSimulatedDelta(targetC.delta_days);
  }

  useEffect(() => {
    checkBackendAndLoad();
    const interval = setInterval(checkBackendAndLoad, 15000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    loadConceptCurve(selectedConceptId);
  }, [selectedConceptId, concepts]);

  // Roll-ups
  const metrics = useMemo(() => {
    if (dashboardData) return dashboardData;

    const total = concepts.length;
    const dueCount = concepts.filter(c => c.is_due).length;
    const weakCount = concepts.filter(c => c.p_hat < 0.65).length;
    const avgStrength = total ? Math.round((concepts.reduce((a, b) => a + b.p_hat, 0) / total) * 100) : 0;

    const subjectsMap = {};
    concepts.forEach(c => {
      if (!subjectsMap[c.subject]) {
        subjectsMap[c.subject] = {
          name: c.subject,
          concepts_count: 0,
          sum_p: 0,
          due_count: 0,
          weak_count: 0,
          priority: settings.subject_priorities[c.subject] || 1.0,
          exam_date: settings.exam_dates[c.subject] || '2026-10-15'
        };
      }
      const s = subjectsMap[c.subject];
      s.concepts_count++;
      s.sum_p += c.p_hat;
      if (c.is_due) s.due_count++;
      if (c.p_hat < 0.65) s.weak_count++;
    });

    const subjectsSummary = Object.values(subjectsMap).map(s => ({
      ...s,
      strength_percent: Math.round((s.sum_p / s.concepts_count) * 100),
      avg_p: parseFloat((s.sum_p / s.concepts_count).toFixed(3))
    }));

    return {
      overall_retention_score: avgStrength,
      total_concepts: total,
      due_concepts_count: dueCount,
      weak_concepts_count: weakCount,
      daily_study_goal_minutes: settings.daily_minutes,
      minutes_studied_today: 32,
      streak_days: 8,
      retention_threshold: settings.retention_threshold,
      subjects: subjectsSummary,
      weakest_concepts: [...concepts].sort((a, b) => a.p_hat - b.p_hat).slice(0, 4)
    };
  }, [dashboardData, concepts, settings]);

  const planSchedule = useMemo(() => {
    if (todayPlan) return todayPlan;

    const subjects = [...new Set(concepts.map(c => c.subject))];
    const dailyMins = settings.daily_minutes;

    const subjectWeights = {};
    subjects.forEach(subj => {
      const subjConcepts = concepts.filter(c => c.subject === subj);
      const avgP = subjConcepts.length ? subjConcepts.reduce((a, b) => a + b.p_hat, 0) / subjConcepts.length : 0.8;
      const dueRatio = subjConcepts.filter(c => c.is_due).length / (subjConcepts.length || 1);
      const prio = settings.subject_priorities[subj] || 1.0;
      subjectWeights[subj] = prio * ((1.0 - avgP) * 2.0 + dueRatio + 0.2);
    });

    const totalWeight = Object.values(subjectWeights).reduce((a, b) => a + b, 0) || 1;
    const blocks = subjects.map(subj => {
      const subjConcepts = concepts.filter(c => c.subject === subj).sort((a, b) => a.p_hat - b.p_hat);
      const allocated = Math.max(10, Math.round(((subjectWeights[subj] / totalWeight) * dailyMins) / 5) * 5);
      return {
        id: `block-${subj.toLowerCase().replace(/\s+/g, '-')}`,
        subject: subj,
        allocated_minutes: allocated,
        estimated_questions: Math.min(8, Math.max(3, subjConcepts.length * 2)),
        avg_p_hat: parseFloat((subjConcepts.reduce((a, b) => a + b.p_hat, 0) / subjConcepts.length).toFixed(3)),
        concepts: subjConcepts.slice(0, 2)
      };
    }).sort((a, b) => a.avg_p_hat - b.avg_p_hat);

    return {
      date: new Date().toISOString().split('T')[0],
      daily_minutes_goal: dailyMins,
      total_scheduled_minutes: blocks.reduce((a, b) => a + b.allocated_minutes, 0),
      due_concepts_total: concepts.filter(c => c.is_due).length,
      blocks
    };
  }, [todayPlan, concepts, settings]);

  // Quiz logic
  function startQuizSession(subject = null, conceptId = null) {
    let pool = [...questions];
    if (subject) {
      pool = pool.filter(q => q.subject.toLowerCase() === subject.toLowerCase());
    }
    if (conceptId) {
      pool = pool.filter(q => q.concept_id === conceptId);
    }
    if (!pool.length) pool = [...questions];

    const picked = pool.sort(() => 0.5 - Math.random()).slice(0, 5);

    setQuizSession({
      active: true,
      subjectFilter: subject,
      conceptFilter: conceptId,
      questions: picked,
      currentIndex: 0,
      selectedOption: null,
      isAnswered: false,
      score: 0,
      completed: false,
      hlrFeedback: null,
      sessionResults: []
    });
    setActiveTab('quiz');
  }

  async function handleOptionSelect(idx) {
    if (quizSession.isAnswered) return;

    const currentQ = quizSession.questions[quizSession.currentIndex];
    const isCorrect = idx === currentQ.answer_index;
    const targetConcept = concepts.find(c => c.id === currentQ.concept_id) || {
      id: currentQ.concept_id,
      name: currentQ.concept_name,
      half_life_days: 1.0,
      n_right: 1,
      n_wrong: 1
    };

    const oldH = targetConcept.half_life_days;
    const projectedH = calcHalfLife(LAUNCH_THETA, [
      1.0,
      targetConcept.n_right + (isCorrect ? 1 : 0),
      targetConcept.n_wrong + (isCorrect ? 0 : 1)
    ]);
    const hChangePct = Math.round(((projectedH - oldH) / oldH) * 100);

    const feedback = {
      isCorrect,
      oldH,
      newH: parseFloat(projectedH.toFixed(3)),
      hChangePct
    };

    if (isApiOnline) {
      fetch(`${API_BASE}/sessions/sess-${Date.now()}/answers`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Student-Id': 'std-default'
        },
        body: JSON.stringify({
          event_id: `evt-${Date.now()}`,
          concept_id: currentQ.concept_id,
          question_id: currentQ.id,
          is_correct: isCorrect,
          selected_index: idx,
          response_time_ms: 1400
        })
      }).catch(e => console.warn(e));
    }

    setQuizSession(prev => ({
      ...prev,
      selectedOption: idx,
      isAnswered: true,
      score: prev.score + (isCorrect ? 1 : 0),
      hlrFeedback: feedback,
      sessionResults: [
        ...prev.sessionResults,
        {
          question: currentQ,
          concept_id: currentQ.concept_id,
          concept_name: currentQ.concept_name,
          isCorrect,
          oldH,
          newH: parseFloat(projectedH.toFixed(3))
        }
      ]
    }));
  }

  function handleNextQuestion() {
    if (quizSession.currentIndex + 1 < quizSession.questions.length) {
      setQuizSession(prev => ({
        ...prev,
        currentIndex: prev.currentIndex + 1,
        selectedOption: null,
        isAnswered: false,
        hlrFeedback: null
      }));
    } else {
      finishQuizSession();
    }
  }

  async function finishQuizSession() {
    const testedConceptIds = [...new Set(quizSession.sessionResults.map(r => r.concept_id))];
    
    setConcepts(prev => prev.map(c => {
      if (!testedConceptIds.includes(c.id)) return c;
      const attempts = quizSession.sessionResults.filter(r => r.concept_id === c.id);
      const rightCount = attempts.filter(a => a.isCorrect).length;
      const wrongCount = attempts.length - rightCount;
      const newRight = c.n_right + rightCount;
      const newWrong = c.n_wrong + wrongCount;
      const newH = calcHalfLife(LAUNCH_THETA, [1.0, newRight, newWrong]);
      const nextRevDays = calcNextReviewDays(newH, settings.retention_threshold);

      return {
        ...c,
        n_right: newRight,
        n_wrong: newWrong,
        half_life_days: parseFloat(newH.toFixed(3)),
        p_hat: 0.99,
        delta_days: 0.0,
        is_due: false,
        next_review_days: parseFloat(nextRevDays.toFixed(1))
      };
    }));

    if (isApiOnline) {
      try {
        await fetch(`${API_BASE}/sessions/sess-${Date.now()}/complete`, { method: 'POST' });
        loadDashboard();
        loadConcepts();
      } catch (e) {
        console.warn(e);
      }
    }

    setQuizSession(prev => ({
      ...prev,
      completed: true
    }));
  }

  async function handleMaterialSubmit(e) {
    e.preventDefault();
    if (!materialForm.title.trim() || !materialForm.content.trim()) return;

    setUploading(true);
    setUploadSuccess(false);

    try {
      if (isApiOnline) {
        const res = await fetch(`${API_BASE}/materials`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(materialForm)
        });
        if (res.ok) {
          const data = await res.json();
          setConcepts(prev => [data.concept, ...prev]);
          setQuestions(prev => [...data.generated_questions, ...prev]);
          setSelectedConceptId(data.concept.id);
          setUploading(false);
          setUploadSuccess(true);
          return;
        }
      }
    } catch (err) {
      console.warn('Backend upload failed, creating client concept', err);
    }

    setTimeout(() => {
      const newId = `c-usr-${Date.now()}`;
      const newConcept = {
        id: newId,
        subject: materialForm.subject,
        topic: materialForm.topic,
        name: materialForm.title,
        difficulty: 'Medium',
        n_right: 0,
        n_wrong: 0,
        days_ago: 0,
        half_life_days: 1.0,
        p_hat: 0.99,
        delta_days: 0.0,
        is_due: false,
        next_review_days: 0.5
      };

      const newQ1 = {
        id: `q-usr-${Date.now()}-1`,
        concept_id: newId,
        concept_name: materialForm.title,
        subject: materialForm.subject,
        text: `Regarding '${materialForm.title}' in ${materialForm.topic}: What primary mechanism distinguishes this concept?`,
        options: [
          `The core invariant established by ${materialForm.title} ensures systemic consistency and bounded latency`,
          'It operates without any memory management or cache coherence',
          'It requires uncoordinated manual overrides across each computational node',
          'It completely removes all transactional guarantees in favor of blind replication'
        ],
        answer_index: 0,
        explanation: `Based on your uploaded study notes for ${materialForm.title}, maintaining systemic consistency and bounded latency is the key invariant.`,
        status: 'draft'
      };

      setConcepts(prev => [newConcept, ...prev]);
      setQuestions(prev => [newQ1, ...prev]);
      setSelectedConceptId(newId);
      setUploading(false);
      setUploadSuccess(true);
    }, 700);
  }

  function handleQuestionStatus(qId, newStatus) {
    setQuestions(prev => prev.map(q => q.id === qId ? { ...q, status: newStatus } : q));
    if (isApiOnline) {
      fetch(`${API_BASE}/questions/${qId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus })
      }).catch(e => console.warn(e));
    }
  }

  const filteredQuestions = useMemo(() => {
    if (questionFilter === 'all') return questions;
    return questions.filter(q => q.status === questionFilter);
  }, [questions, questionFilter]);

  return (
    <div className="app-container">
      {/* ================= HEADER BAR ================= */}
      <header className="header-bar">
        <div className="header-inner">
          <div className="brand-section" onClick={() => setActiveTab('dashboard')}>
            <div className="brand-icon-box">
              <Brain size={20} />
            </div>
            <div className="brand-titles">
              <span className="brand-name">FocusFlow</span>
              <span className="brand-badge">HLR Engine v2.0</span>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="nav-tabs">
            <button
              className={`nav-tab-btn ${activeTab === 'dashboard' ? 'active' : ''}`}
              onClick={() => setActiveTab('dashboard')}
            >
              <Layers size={14} /> Dashboard
            </button>
            <button
              className={`nav-tab-btn ${activeTab === 'plan' ? 'active' : ''}`}
              onClick={() => setActiveTab('plan')}
            >
              <Calendar size={14} /> Today's Plan
            </button>
            <button
              className={`nav-tab-btn ${activeTab === 'quiz' ? 'active' : ''}`}
              onClick={() => setActiveTab('quiz')}
            >
              <Zap size={14} /> Quiz Mode
            </button>
            <button
              className={`nav-tab-btn ${activeTab === 'chat' ? 'active' : ''}`}
              onClick={() => setActiveTab('chat')}
            >
              <MessageSquare size={14} /> AI Buddy
            </button>
            <button
              className={`nav-tab-btn ${activeTab === 'doubts' ? 'active' : ''}`}
              onClick={() => setActiveTab('doubts')}
            >
              <HelpCircle size={14} /> Doubt Solver
            </button>
            <button
              className={`nav-tab-btn ${activeTab === 'mnemonics' ? 'active' : ''}`}
              onClick={() => setActiveTab('mnemonics')}
            >
              <Sparkles size={14} /> Mnemonic Lab
            </button>
            <button
              className={`nav-tab-btn ${activeTab === 'materials' ? 'active' : ''}`}
              onClick={() => setActiveTab('materials')}
            >
              <BookOpen size={14} /> Materials & AI
            </button>
            <button
              className={`nav-tab-btn ${activeTab === 'curve' ? 'active' : ''}`}
              onClick={() => setActiveTab('curve')}
            >
              <LineChart size={14} /> Forgetting Curve
            </button>
            <button
              className={`nav-tab-btn ${activeTab === 'settings' ? 'active' : ''}`}
              onClick={() => setActiveTab('settings')}
            >
              <Settings size={14} /> Settings
            </button>
          </nav>

          {/* Header Utilities */}
          <div className="header-actions">
            <div className="streak-pill">
              <Flame size={13} /> 8d Streak
            </div>
            <div className="engine-status-pill">
              <span className="status-dot"></span>
              {isApiOnline ? 'HLR Online' : 'Local Engine'}
            </div>
            <button
              className="btn-secondary btn-sm"
              onClick={() => setShowOnboarding(true)}
              title="Setup study parameters"
            >
              <Sliders size={13} /> Setup
            </button>
          </div>
        </div>
      </header>

      {/* ================= MAIN CONTAINER ================= */}
      <main className="main-wrapper">
        {/* ================= SCREEN 1: DASHBOARD ================= */}
        {activeTab === 'dashboard' && (
          <div className="animate-fade-in">
            {/* Top Metric Cards */}
            <div className="metrics-grid">
              <div className="glass-card metric-card">
                <div>
                  <div className="metric-label">
                    <Brain size={13} /> Overall Retention
                  </div>
                  <div className="metric-value" style={{ color: metrics.overall_retention_score >= 70 ? 'var(--mint-dark)' : 'var(--coral)' }}>
                    {metrics.overall_retention_score}%
                  </div>
                  <div className="metric-sub">Target: {Math.round(metrics.retention_threshold * 100)}% minimum</div>
                </div>
                <div className="metric-icon-box">
                  <TrendingUp size={18} />
                </div>
              </div>

              <div className="glass-card metric-card">
                <div>
                  <div className="metric-label">
                    <Clock size={13} /> Due For Review
                  </div>
                  <div className="metric-value" style={{ color: metrics.due_concepts_count > 0 ? 'var(--coral)' : 'var(--mint-dark)' }}>
                    {metrics.due_concepts_count}
                  </div>
                  <div className="metric-sub">{metrics.due_concepts_count > 0 ? 'Urgent memory decay' : 'All caught up'}</div>
                </div>
                <div className="metric-icon-box" style={{ color: 'var(--coral)' }}>
                  <AlertTriangle size={18} />
                </div>
              </div>

              <div className="glass-card metric-card">
                <div>
                  <div className="metric-label">
                    <Award size={13} /> Total Concepts
                  </div>
                  <div className="metric-value">{metrics.total_concepts}</div>
                  <div className="metric-sub">{metrics.weak_concepts_count} at critical threshold</div>
                </div>
                <div className="metric-icon-box">
                  <Database size={18} />
                </div>
              </div>

              <div className="glass-card metric-card">
                <div>
                  <div className="metric-label">
                    <Clock size={13} /> Daily Study Goal
                  </div>
                  <div className="metric-value">
                    {metrics.minutes_studied_today} <span style={{ fontSize: 16, color: 'var(--muted)' }}>/ {metrics.daily_study_goal_minutes}m</span>
                  </div>
                  <div className="metric-sub">71% daily budget complete</div>
                </div>
                <div className="metric-icon-box" style={{ color: 'var(--mint-dark)' }}>
                  <Flame size={18} />
                </div>
              </div>
            </div>

            {/* Quick Action Banner */}
            <div
              className="glass-card"
              style={{
                marginBottom: 26,
                background: 'var(--mint-bg)',
                border: '1px solid #c2e2cf',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: 14
              }}
            >
              <div>
                <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 3, display: 'flex', alignItems: 'center', gap: 7, color: 'var(--ink)' }}>
                  <Sparkles size={16} color="var(--mint-dark)" /> Recommended Spaced Review Session
                </h3>
                <p style={{ fontSize: 13, color: 'var(--mint-dark)' }}>
                  HLR engine identified <b>{metrics.due_concepts_count} concepts</b> falling below the 70% threshold. Practice now to extend half-life before retention decays.
                </p>
              </div>
              <button
                className="btn-primary"
                onClick={() => startQuizSession()}
                style={{ padding: '10px 20px', fontSize: 13 }}
              >
                <Play size={14} /> Start Smart Review ({metrics.due_concepts_count || 4} Concepts)
              </button>
            </div>

            {/* Subject Retention Breakdown */}
            <div className="section-header">
              <div>
                <h2 className="section-title">
                  <Layers size={17} /> Subject Retention Strength
                </h2>
                <span className="section-subtitle">Estimated memory stability and upcoming exam countdowns</span>
              </div>
            </div>

            <div className="subjects-grid">
              {metrics.subjects.map(subj => {
                const color = subj.strength_percent >= 80 ? 'var(--mint-dark)' : subj.strength_percent >= 65 ? 'var(--yellow-dark)' : 'var(--coral)';
                const barColor = subj.strength_percent >= 80 ? 'var(--mint)' : subj.strength_percent >= 65 ? 'var(--yellow)' : 'var(--coral)';
                return (
                  <div key={subj.name} className="glass-card subject-card">
                    <div>
                      <div className="subject-header">
                        <span className="subject-title">{subj.name}</span>
                        <span className="subject-exam-badge">
                          Exam: {subj.exam_date}
                        </span>
                      </div>
                      <div className="subject-stats-row" style={{ marginTop: 12, marginBottom: 6 }}>
                        <span>Memory Strength</span>
                        <span className="strength-pct-pill" style={{ color }}>{subj.strength_percent}%</span>
                      </div>
                      <div className="progress-bar-container">
                        <div className="progress-bar-fill" style={{ width: `${subj.strength_percent}%`, background: barColor }}></div>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 10, fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>
                        <span>{subj.concepts_count} concepts</span>
                        <span style={{ color: subj.due_count > 0 ? 'var(--coral)' : 'inherit' }}>
                          {subj.due_count} due for review
                        </span>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                      <button
                        className="btn-secondary btn-sm"
                        style={{ flex: 1 }}
                        onClick={() => {
                          const firstConcept = concepts.find(c => c.subject === subj.name);
                          if (firstConcept) setSelectedConceptId(firstConcept.id);
                          setActiveTab('curve');
                        }}
                      >
                        <LineChart size={12} /> Curve
                      </button>
                      <button
                        className="btn-primary btn-sm"
                        style={{ flex: 1.2 }}
                        onClick={() => startQuizSession(subj.name)}
                      >
                        <Play size={12} /> Practice
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Critical Concepts Needing Review */}
            <div className="section-header" style={{ marginTop: 30 }}>
              <div>
                <h2 className="section-title">
                  <TrendingDown size={17} color="var(--coral)" /> Weakest Concepts (Lowest Recall Probability)
                </h2>
                <span className="section-subtitle">Rank ordered for optimal spaced repetition</span>
              </div>
            </div>

            <div className="glass-card" style={{ padding: 0, overflow: 'hidden' }}>
              <table className="modern-table">
                <thead>
                  <tr>
                    <th>Concept & Topic</th>
                    <th>Subject</th>
                    <th>Elapsed (Δ)</th>
                    <th>Predicted Recall (p̂)</th>
                    <th>Half-life (ĥ)</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {metrics.weakest_concepts.map(c => (
                    <tr key={c.id}>
                      <td>
                        <div style={{ fontWeight: 700, color: 'var(--ink)' }}>{c.name}</div>
                        <div style={{ fontSize: 11, color: 'var(--muted)' }}>{c.topic}</div>
                      </td>
                      <td>
                        <span style={{ fontSize: 12, color: 'var(--muted)' }}>{c.subject}</span>
                      </td>
                      <td>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{c.delta_days} days</span>
                      </td>
                      <td>
                        <span
                          className={`badge ${c.p_hat <= 0.70 ? 'badge-due' : 'badge-medium'}`}
                        >
                          {(c.p_hat * 100).toFixed(1)}%
                        </span>
                      </td>
                      <td>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                          {c.half_life_days}d
                        </span>
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: 5 }}>
                          <button
                            className="btn-secondary btn-sm"
                            title="Generate Memory Anchors & Mnemonics"
                            onClick={() => {
                              setMnemonicConcept(c.name);
                              setMnemonicSubject(c.subject);
                              handleGenerateMnemonic(c.name, c.subject);
                              setActiveTab('mnemonics');
                            }}
                          >
                            <Sparkles size={11} color="var(--yellow-dark)" /> Mnemonic
                          </button>
                          <button
                            className="btn-secondary btn-sm"
                            title="Solve doubt on this concept"
                            onClick={() => {
                              setDoubtConcept(c.name);
                              setDoubtSubject(c.subject);
                              setDoubtInput(`I have a doubt about ${c.name} in ${c.subject}: What is the core mechanism and what common mistakes should I avoid?`);
                              setActiveTab('doubts');
                            }}
                          >
                            <HelpCircle size={11} color="var(--mint-dark)" /> Doubt
                          </button>
                          <button
                            className="btn-secondary btn-sm"
                            onClick={() => {
                              setSelectedConceptId(c.id);
                              setActiveTab('curve');
                            }}
                          >
                            <LineChart size={11} /> Curve
                          </button>
                          <button
                            className="btn-primary btn-sm"
                            onClick={() => startQuizSession(null, c.id)}
                          >
                            <Play size={11} /> Quiz
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ================= SCREEN 2: TODAY'S PLAN ================= */}
        {activeTab === 'plan' && (
          <div className="animate-fade-in">
            <div className="section-header">
              <div>
                <h1 className="section-title">
                  <Calendar size={18} /> Adaptive HLR Study Plan
                </h1>
                <span className="section-subtitle">
                  Daily allocation: Minutes weighted by memory decay gradient (1 - p̂) and exam urgency.
                </span>
              </div>
              <div>
                <div className="badge badge-medium" style={{ padding: '6px 12px', fontSize: 11 }}>
                  <Clock size={12} /> Planned: {planSchedule.total_scheduled_minutes}m / {planSchedule.daily_minutes_goal}m
                </div>
              </div>
            </div>

            <div className="plan-blocks-list" style={{ marginTop: 20 }}>
              {planSchedule.blocks.map(block => (
                <div key={block.id} className="plan-block-card">
                  <div className="plan-block-main">
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                      <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--ink)' }}>{block.subject}</h3>
                      <span className="badge badge-easy">
                        <Clock size={11} /> {block.allocated_minutes} Minutes
                      </span>
                      <span className="badge badge-medium">
                        ~{block.estimated_questions} Questions
                      </span>
                      <span style={{ fontSize: 12, color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>
                        Avg Recall: {Math.round(block.avg_p_hat * 100)}%
                      </span>
                    </div>

                    <div className="plan-concepts-chips">
                      <span style={{ fontSize: 11, color: 'var(--muted)', alignSelf: 'center', fontFamily: 'var(--font-mono)' }}>Concepts:</span>
                      {block.concepts.map(c => (
                        <div
                          key={c.id}
                          className="concept-chip"
                          onClick={() => {
                            setSelectedConceptId(c.id);
                            setActiveTab('curve');
                          }}
                        >
                          <span>{c.name}</span>
                          <span style={{ color: c.p_hat <= 0.70 ? 'var(--coral)' : 'var(--mint-dark)', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
                            {Math.round(c.p_hat * 100)}%
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div>
                    <button
                      className="btn-primary"
                      onClick={() => startQuizSession(block.subject)}
                      style={{ padding: '8px 16px', whiteSpace: 'nowrap' }}
                    >
                      <Play size={13} /> Start Session
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {/* 7-Day Memory Decay Forecast */}
            <div className="glass-card" style={{ marginTop: 28 }}>
              <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 7 }}>
                <TrendingDown size={15} color="var(--mint-dark)" /> 7-Day Projected Memory Decay Forecast
              </h3>
              <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 18 }}>
                Estimated count of concepts dropping below the 70% retention threshold:
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 10 }}>
                {['Today', 'Tomorrow', '+2 Days', '+3 Days', '+4 Days', '+5 Days', '+6 Days'].map((dayLabel, idx) => {
                  const projectedCount = Math.min(concepts.length, metrics.due_concepts_count + idx * 2);
                  return (
                    <div
                      key={dayLabel}
                      style={{
                        padding: 12,
                        borderRadius: 'var(--radius-sm)',
                        background: idx === 0 ? 'var(--mint-bg)' : '#f0ede6',
                        border: idx === 0 ? '1px solid #c2e2cf' : '1px solid var(--line)',
                        textAlign: 'center'
                      }}
                    >
                      <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--muted)' }}>{dayLabel}</div>
                      <div style={{ fontSize: 20, fontWeight: 800, marginTop: 4, color: projectedCount > 4 ? 'var(--coral)' : 'var(--mint-dark)' }}>
                        {projectedCount} Due
                      </div>
                      <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--muted)', marginTop: 2 }}>{idx === 0 ? 'Active' : 'Forecast'}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* ================= SCREEN 3: QUIZ MODE ================= */}
        {activeTab === 'quiz' && (
          <div className="animate-fade-in quiz-wrapper">
            {!quizSession.active && !quizSession.completed && (
              <div className="glass-card" style={{ textAlign: 'center', padding: '44px 20px' }}>
                <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'var(--mint-bg)', display: 'grid', placeItems: 'center', margin: '0 auto 16px', color: 'var(--mint-dark)' }}>
                  <Zap size={28} />
                </div>
                <h2 style={{ fontSize: 20, fontWeight: 800, marginBottom: 8 }}>Ready for Focused Active Recall?</h2>
                <p style={{ color: 'var(--muted)', maxWidth: 480, margin: '0 auto 20px', fontSize: 13 }}>
                  Questions are dynamically selected to target concepts with the highest memory decay rate. Instant explanations and real-time HLR half-life updates follow every answer.
                </p>
                <button
                  className="btn-primary"
                  onClick={() => startQuizSession()}
                  style={{ padding: '10px 24px', fontSize: 13 }}
                >
                  <Play size={14} /> Begin Targeted Session (5 Questions)
                </button>
              </div>
            )}

            {quizSession.active && !quizSession.completed && (
              <div>
                <div className="quiz-top-bar">
                  <div>
                    <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--muted)' }}>
                      Question {quizSession.currentIndex + 1} of {quizSession.questions.length}
                    </span>
                    <h4 style={{ fontSize: 14, fontWeight: 700, color: 'var(--mint-dark)' }}>
                      {quizSession.questions[quizSession.currentIndex]?.subject}
                    </h4>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span className="badge badge-medium">
                      {quizSession.questions[quizSession.currentIndex]?.concept_name}
                    </span>
                    <button
                      className="btn-secondary btn-sm"
                      onClick={() => setQuizSession(prev => ({ ...prev, active: false }))}
                    >
                      Exit
                    </button>
                  </div>
                </div>

                <div className="progress-bar-container" style={{ marginBottom: 20 }}>
                  <div
                    className="progress-bar-fill"
                    style={{
                      width: `${((quizSession.currentIndex + 1) / quizSession.questions.length) * 100}%`,
                      background: 'var(--mint-dark)'
                    }}
                  ></div>
                </div>

                <div className="glass-card quiz-card">
                  <div className="quiz-question-text">
                    {quizSession.questions[quizSession.currentIndex]?.text}
                  </div>

                  <div className="quiz-options-list">
                    {quizSession.questions[quizSession.currentIndex]?.options.map((opt, idx) => {
                      const isSelected = quizSession.selectedOption === idx;
                      const isCorrectAnswer = idx === quizSession.questions[quizSession.currentIndex]?.answer_index;
                      let statusClass = '';

                      if (quizSession.isAnswered) {
                        if (isCorrectAnswer) statusClass = 'correct';
                        else if (isSelected) statusClass = 'incorrect';
                      } else if (isSelected) {
                        statusClass = 'selected';
                      }

                      return (
                        <button
                          key={idx}
                          className={`quiz-option-btn ${statusClass}`}
                          onClick={() => handleOptionSelect(idx)}
                          disabled={quizSession.isAnswered}
                        >
                          <span className="quiz-option-key">
                            {['A', 'B', 'C', 'D'][idx]}
                          </span>
                          <span style={{ flex: 1 }}>{opt}</span>
                          {quizSession.isAnswered && isCorrectAnswer && (
                            <Check size={16} color="var(--mint-dark)" />
                          )}
                          {quizSession.isAnswered && isSelected && !isCorrectAnswer && (
                            <X size={16} color="var(--coral)" />
                          )}
                        </button>
                      );
                    })}
                  </div>

                  {quizSession.isAnswered && (
                    <div className="quiz-explanation-box">
                      {quizSession.hlrFeedback && (
                        <div className={`hlr-feedback-banner ${quizSession.hlrFeedback.isCorrect ? 'positive' : 'negative'}`}>
                          {quizSession.hlrFeedback.isCorrect ? (
                            <>
                              <TrendingUp size={15} />
                              <span>
                                Active Recall Reinforced! Half-life ĥ extended: {quizSession.hlrFeedback.oldH}d → {quizSession.hlrFeedback.newH}d (+{quizSession.hlrFeedback.hChangePct}%)
                              </span>
                            </>
                          ) : (
                            <>
                              <TrendingDown size={15} />
                              <span>
                                Memory Lapse Detected! Half-life ĥ adjusted: {quizSession.hlrFeedback.oldH}d → {quizSession.hlrFeedback.newH}d ({quizSession.hlrFeedback.hChangePct}%)
                              </span>
                            </>
                          )}
                        </div>
                      )}

                      <h4 style={{ fontSize: 13, fontWeight: 700, marginBottom: 4, display: 'flex', alignItems: 'center', gap: 5, color: 'var(--ink)' }}>
                        <HelpCircle size={14} color="var(--mint-dark)" /> Explanation
                      </h4>
                      <p style={{ fontSize: 13, color: 'var(--ink)', lineHeight: 1.6 }}>
                        {quizSession.questions[quizSession.currentIndex]?.explanation}
                      </p>

                      <div style={{ marginTop: 18, display: 'flex', justifyContent: 'flex-end' }}>
                        <button
                          className="btn-primary"
                          onClick={handleNextQuestion}
                          style={{ padding: '9px 20px' }}
                        >
                          {quizSession.currentIndex + 1 < quizSession.questions.length ? (
                            <>Next Question <ArrowRight size={14} /></>
                          ) : (
                            <>Complete Session <CheckCircle2 size={14} /></>
                          )}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {quizSession.completed && (
              <div className="glass-card animate-fade-in" style={{ padding: 36, textAlign: 'center' }}>
                <div style={{ width: 64, height: 64, borderRadius: '50%', background: 'var(--mint-bg)', display: 'grid', placeItems: 'center', margin: '0 auto 14px', color: 'var(--mint-dark)' }}>
                  <Award size={32} />
                </div>
                <h2 style={{ fontSize: 22, fontWeight: 800, marginBottom: 6 }}>Session Successfully Completed!</h2>
                <p style={{ color: 'var(--muted)', fontSize: 14, marginBottom: 22 }}>
                  You scored <b>{quizSession.score}</b> out of <b>{quizSession.questions.length}</b> ({Math.round((quizSession.score / quizSession.questions.length) * 100)}%).
                </p>

                <div style={{ textAlign: 'left', marginBottom: 24 }}>
                  <h4 style={{ fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 10 }}>
                    HLR Concept State Updates:
                  </h4>
                  <div style={{ background: '#f6f3eb', borderRadius: 'var(--radius-sm)', border: '1px solid var(--line)', padding: 10 }}>
                    {quizSession.sessionResults.map((r, i) => (
                      <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 10px', borderBottom: i < quizSession.sessionResults.length - 1 ? '1px solid var(--line)' : 'none' }}>
                        <div>
                          <span style={{ fontWeight: 700, fontSize: 13, color: 'var(--ink)' }}>{r.concept_name}</span>
                          <span style={{ marginLeft: 8, fontSize: 11, fontFamily: 'var(--font-mono)', color: r.isCorrect ? 'var(--mint-dark)' : 'var(--coral)' }}>
                            {r.isCorrect ? '✓ Correct' : '✗ Missed'}
                          </span>
                        </div>
                        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--ink)' }}>
                          ĥ: {r.oldH}d → <b>{r.newH}d</b>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap' }}>
                  <button className="btn-secondary" onClick={() => setActiveTab('dashboard')}>
                    Return to Dashboard
                  </button>
                  <button
                    className="btn-secondary"
                    onClick={() => {
                      const missed = quizSession.sessionResults.filter(r => !r.isCorrect);
                      const subj = quizSession.questions[0]?.subject || 'All';
                      setChatSubject(subj);
                      if (missed.length > 0) {
                        setChatInput(`I just missed "${missed.map(m => m.concept_name).join(', ')}" in my quiz. Can you act as my Socratic tutor and help me discover where my misunderstanding is?`);
                      } else {
                        setChatInput(`I scored 100% on my recent quiz! What advanced edge cases or tricky exam questions should I practice next?`);
                      }
                      setActiveTab('chat');
                    }}
                  >
                    <MessageSquare size={14} color="var(--mint-dark)" /> Discuss with AI Buddy
                  </button>
                  <button className="btn-secondary" onClick={() => setActiveTab('curve')}>
                    <LineChart size={14} /> View Forgetting Curves
                  </button>
                  <button className="btn-primary" onClick={() => startQuizSession()}>
                    <RotateCcw size={14} /> Start Another Session
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ================= SCREEN: AI STUDY BUDDY (CHATBOT) ================= */}
        {activeTab === 'chat' && (
          <div className="animate-fade-in chat-window">
            <div className="chat-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'var(--mint-bg)', border: '1px solid var(--mint)', display: 'grid', placeItems: 'center', color: 'var(--mint-dark)' }}>
                  <Bot size={18} />
                </div>
                <div>
                  <h3 style={{ fontSize: 14, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}>
                    Socratic AI Study Buddy
                    <span className="badge badge-easy" style={{ fontSize: 10 }}>Gemini 2.0</span>
                  </h3>
                  <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                    Active recall tutor grounded in your memory half-life metrics
                  </span>
                </div>
              </div>

              {/* Persona and Subject Controls */}
              <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                <div className="persona-selector">
                  <button
                    className={`persona-pill ${chatPersona === 'socratic' ? 'active' : ''}`}
                    onClick={() => setChatPersona('socratic')}
                    title="Active recall tutor that asks guiding questions"
                  >
                    🧠 Socratic Tutor
                  </button>
                  <button
                    className={`persona-pill ${chatPersona === 'exam_prep' ? 'active' : ''}`}
                    onClick={() => setChatPersona('exam_prep')}
                    title="High-yield exam summaries and edge-cases"
                  >
                    🎯 Exam Coach
                  </button>
                  <button
                    className={`persona-pill ${chatPersona === 'eli5' ? 'active' : ''}`}
                    onClick={() => setChatPersona('eli5')}
                    title="Simple analogies with zero jargon"
                  >
                    💡 ELI5 Explainer
                  </button>
                </div>

                <select
                  className="select-input"
                  style={{ width: 'auto', padding: '5px 10px', fontSize: 11 }}
                  value={chatSubject}
                  onChange={e => setChatSubject(e.target.value)}
                >
                  <option value="All">All Subjects</option>
                  <option value="Artificial Intelligence">AI & Neural Nets</option>
                  <option value="Operating Systems">Operating Systems</option>
                  <option value="Mathematics">Mathematics</option>
                  <option value="Distributed Systems">Distributed Systems</option>
                </select>

                <button
                  className="btn-secondary btn-sm"
                  onClick={() => setChatMessages([
                    {
                      role: 'model',
                      content: "Chat cleared! What new concept or doubt would you like to master?",
                      timestamp: 'Just now',
                      followups: [
                        "Quiz me on my weakest concept",
                        "Explain Bayes Theorem & Posterior Update",
                        "How do I prevent memory decay in Distributed Systems?"
                      ]
                    }
                  ])}
                  title="Reset conversation"
                >
                  <RotateCcw size={12} /> Clear
                </button>
              </div>
            </div>

            {/* Chat Feed */}
            <div className="chat-feed">
              {chatMessages.map((msg, idx) => (
                <div key={idx} className={`chat-msg-row ${msg.role === 'user' ? 'user' : 'ai'}`}>
                  <div className={`chat-avatar ${msg.role === 'user' ? 'user-av' : 'ai-av'}`}>
                    {msg.role === 'user' ? 'U' : <Sparkles size={15} />}
                  </div>
                  <div>
                    <div className={`chat-bubble ${msg.role === 'user' ? 'user' : 'ai'}`}>
                      <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                    </div>
                    <div className="chat-meta">
                      <span>{msg.timestamp}</span>
                      {msg.aiPowered && <span style={{ color: 'var(--mint-dark)' }}>• Gemini Live</span>}
                    </div>

                    {msg.followups && msg.followups.length > 0 && (
                      <div className="chat-chip-container">
                        {msg.followups.map((chip, cIdx) => (
                          <button
                            key={cIdx}
                            className="chat-suggestion-chip"
                            onClick={() => handleSendChatMessage(chip)}
                          >
                            ↳ {chip}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {chatLoading && (
                <div className="chat-msg-row ai">
                  <div className="chat-avatar ai-av">
                    <Sparkles size={15} />
                  </div>
                  <div className="chat-bubble ai" style={{ color: 'var(--muted)', fontStyle: 'italic', display: 'flex', alignItems: 'center', gap: 8 }}>
                    <RefreshCw size={13} className="animate-spin" /> FocusFlow AI is thinking...
                  </div>
                </div>
              )}
            </div>

            {/* Chat Input Bar */}
            <div className="chat-input-bar">
              <input
                type="text"
                className="chat-input-field"
                placeholder={chatLoading ? "AI is generating..." : `Ask your study buddy anything about ${chatSubject === 'All' ? 'your subjects' : chatSubject}... (e.g. 'Test me on Raft terms')`}
                value={chatInput}
                disabled={chatLoading}
                onChange={e => setChatInput(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') {
                    handleSendChatMessage();
                  }
                }}
              />
              <button
                className="btn-primary"
                style={{ padding: '10px 18px', display: 'flex', alignItems: 'center', gap: 6 }}
                onClick={() => handleSendChatMessage()}
                disabled={chatLoading || !chatInput.trim()}
              >
                <Send size={14} /> Send
              </button>
            </div>
          </div>
        )}

        {/* ================= SCREEN: DOUBT SOLVER ================= */}
        {activeTab === 'doubts' && (
          <div className="animate-fade-in" style={{ maxWidth: 940, margin: '0 auto' }}>
            <div className="section-header">
              <div>
                <h1 className="section-title">
                  <HelpCircle size={18} /> Deep Concept Doubt Solver
                </h1>
                <span className="section-subtitle">
                  Ask any difficult problem, code snippet, or theoretical confusion. Gemini decomposes it into core intuition, step-by-step logic, common traps, and instant verification challenges.
                </span>
              </div>
            </div>

            <div className="glass-card" style={{ marginTop: 18, marginBottom: 20 }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12, marginBottom: 14 }}>
                <div className="input-group">
                  <label className="input-label">Subject</label>
                  <select
                    className="select-input"
                    value={doubtSubject}
                    onChange={e => setDoubtSubject(e.target.value)}
                  >
                    <option value="Operating Systems">Operating Systems</option>
                    <option value="Artificial Intelligence">Artificial Intelligence</option>
                    <option value="Distributed Systems">Distributed Systems</option>
                    <option value="Mathematics">Mathematics</option>
                    <option value="Computer Science">Computer Science General</option>
                  </select>
                </div>

                <div className="input-group">
                  <label className="input-label">Target Concept (Optional)</label>
                  <select
                    className="select-input"
                    value={doubtConcept}
                    onChange={e => setDoubtConcept(e.target.value)}
                  >
                    <option value="">General Subject Doubt</option>
                    {concepts.map(c => (
                      <option key={c.id} value={c.name}>{c.name}</option>
                    ))}
                  </select>
                </div>

                <div className="input-group">
                  <label className="input-label">Difficulty Expectation</label>
                  <select
                    className="select-input"
                    value={doubtDifficulty}
                    onChange={e => setDoubtDifficulty(e.target.value)}
                  >
                    <option value="Easy">Beginner / Intuitive</option>
                    <option value="Medium">Undergraduate Exam Level</option>
                    <option value="Hard">Advanced / Rigorous</option>
                  </select>
                </div>
              </div>

              <div className="input-group">
                <label className="input-label">Describe your doubt or paste problem statement</label>
                <textarea
                  className="textarea-input"
                  rows={4}
                  placeholder="e.g. Why does Transformer self-attention divide Query-Key dot products by sqrt(d_k)? What happens to the gradients if we omit this?"
                  value={doubtInput}
                  onChange={e => setDoubtInput(e.target.value)}
                />
              </div>

              {/* Sample Doubts Quick Buttons */}
              <div style={{ marginBottom: 16 }}>
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--muted)', display: 'block', marginBottom: 6 }}>
                  Quick Sample Doubts:
                </span>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {[
                    "Why divide query-key dot product by sqrt(d_k) in Transformers?",
                    "How does Clock page replacement approximate LRU without a linked list?",
                    "Difference between CAP consistency vs ACID consistency?",
                    "Why does Ebbinghaus forgetting curve decay exponentially?"
                  ].map((preset, idx) => (
                    <button
                      key={idx}
                      className="chat-suggestion-chip"
                      onClick={() => handleSolveDoubt(preset)}
                    >
                      {preset}
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                <button
                  className="btn-primary"
                  onClick={() => handleSolveDoubt()}
                  disabled={doubtLoading || !doubtInput.trim()}
                  style={{ padding: '10px 22px', display: 'flex', alignItems: 'center', gap: 6 }}
                >
                  {doubtLoading ? <RefreshCw size={14} className="animate-spin" /> : <HelpCircle size={14} />}
                  {doubtLoading ? 'Analyzing Doubt with Gemini...' : 'Deconstruct & Solve Doubt'}
                </button>
              </div>
            </div>

            {/* Doubt Solution Card */}
            {doubtResult && (
              <div className="animate-fade-in doubt-grid">
                {/* 1. Core Intuition */}
                <div className="solution-box" style={{ borderLeft: '4px solid var(--mint-dark)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                    <Lightbulb size={18} color="var(--yellow-dark)" />
                    <h3 style={{ fontSize: 15, fontWeight: 700 }}>The Core Intuition</h3>
                    {doubtResult.ai_powered && <span className="badge badge-easy">Gemini Verified</span>}
                  </div>
                  <p style={{ fontSize: 13, color: 'var(--ink)', lineHeight: 1.6 }}>
                    {doubtResult.core_intuition}
                  </p>
                </div>

                {/* 2. Step-by-Step Logic Trace */}
                <div className="solution-box">
                  <h4 style={{ fontSize: 14, fontWeight: 700, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 7 }}>
                    <CheckCircle2 size={15} color="var(--mint-dark)" /> Step-by-Step Logical Resolution
                  </h4>
                  {doubtResult.step_by_step_solution.map((step, sIdx) => (
                    <div key={sIdx} className="step-item">
                      <div className="step-num">{sIdx + 1}</div>
                      <div style={{ fontSize: 13, lineHeight: 1.5, color: 'var(--ink)' }}>{step}</div>
                    </div>
                  ))}
                </div>

                {/* 3. Pitfalls & Retention Hook */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14 }}>
                  <div className="pitfall-box">
                    <h4 style={{ fontSize: 13, fontWeight: 700, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6, color: 'var(--coral-dark)' }}>
                      <AlertTriangle size={15} /> Common Traps & Exam Pitfalls
                    </h4>
                    <ul style={{ paddingLeft: 18, fontSize: 12, lineHeight: 1.6 }}>
                      {doubtResult.common_pitfalls.map((pitfall, pIdx) => (
                        <li key={pIdx}>{pitfall}</li>
                      ))}
                    </ul>
                  </div>

                  <div className="retention-hook-box">
                    <h4 style={{ fontSize: 13, fontWeight: 700, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6, color: 'var(--mint-dark)' }}>
                      <Sparkles size={15} /> Memory Retention Anchor
                    </h4>
                    <p style={{ fontSize: 12, lineHeight: 1.6, fontWeight: 600 }}>
                      {doubtResult.retention_hook}
                    </p>
                  </div>
                </div>

                {/* 4. Instant Verification Challenge */}
                {doubtResult.verification_challenge && (
                  <div className="solution-box" style={{ background: '#fdfbf7', border: '1px solid #ebd9c5' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                      <h4 style={{ fontSize: 14, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Zap size={15} color="var(--yellow-dark)" /> Instant Comprehension Check
                      </h4>
                      <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--muted)' }}>
                        Verify your understanding
                      </span>
                    </div>

                    <p style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>
                      {doubtResult.verification_challenge.question}
                    </p>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {doubtResult.verification_challenge.options.map((opt, optIdx) => {
                        const isCorrect = optIdx === doubtResult.verification_challenge.answer_index;
                        const isSelected = selectedChallengeOption === optIdx;
                        let btnStyle = { padding: '10px 14px', textAlign: 'left', borderRadius: 'var(--radius-sm)', border: '1px solid var(--line)', background: '#ffffff', fontSize: 12, cursor: 'pointer' };
                        if (selectedChallengeOption !== null) {
                          if (isCorrect) {
                            btnStyle = { ...btnStyle, background: 'var(--mint-bg)', borderColor: 'var(--mint)', color: 'var(--mint-dark)', fontWeight: 700 };
                          } else if (isSelected) {
                            btnStyle = { ...btnStyle, background: 'var(--coral-bg)', borderColor: 'var(--coral)', color: 'var(--coral-dark)' };
                          }
                        }
                        return (
                          <button
                            key={optIdx}
                            style={btnStyle}
                            onClick={() => setSelectedChallengeOption(optIdx)}
                          >
                            <span style={{ fontWeight: 700, marginRight: 8 }}>{String.fromCharCode(65 + optIdx)}.</span>
                            {opt}
                          </button>
                        );
                      })}
                    </div>

                    {selectedChallengeOption !== null && (
                      <div style={{ marginTop: 12, padding: 10, borderRadius: 'var(--radius-sm)', background: selectedChallengeOption === doubtResult.verification_challenge.answer_index ? 'var(--mint-bg)' : 'var(--coral-bg)', fontSize: 12 }}>
                        <b>{selectedChallengeOption === doubtResult.verification_challenge.answer_index ? '✓ Exactly Right!' : '✗ Not quite:'}</b> {doubtResult.verification_challenge.explanation}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ================= SCREEN: MNEMONIC LAB & MEMORY ANCHORS ================= */}
        {activeTab === 'mnemonics' && (
          <div className="animate-fade-in" style={{ maxWidth: 940, margin: '0 auto' }}>
            <div className="section-header">
              <div>
                <h1 className="section-title">
                  <Sparkles size={18} /> AI Memory Anchor & Mnemonic Lab
                </h1>
                <span className="section-subtitle">
                  Supercharge your memory half-life (h). Convert abstract computer science theorems and algorithms into vivid narrative mnemonics and interactive active recall flashcards.
                </span>
              </div>
            </div>

            <div className="glass-card" style={{ marginTop: 18, marginBottom: 20 }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14 }}>
                <div className="input-group">
                  <label className="input-label">Select from your concepts</label>
                  <select
                    className="select-input"
                    value={mnemonicConcept}
                    onChange={e => {
                      setMnemonicConcept(e.target.value);
                      const match = concepts.find(c => c.name === e.target.value);
                      if (match) setMnemonicSubject(match.subject);
                    }}
                  >
                    {concepts.map(c => (
                      <option key={c.id} value={c.name}>{c.name} ({c.subject})</option>
                    ))}
                  </select>
                </div>

                <div className="input-group">
                  <label className="input-label">Or Type Custom Concept Name</label>
                  <input
                    type="text"
                    className="text-input"
                    placeholder="e.g. Paxos Consensus or Eigenvalues"
                    value={mnemonicConcept}
                    onChange={e => setMnemonicConcept(e.target.value)}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 12 }}>
                <button
                  className="btn-primary"
                  onClick={() => handleGenerateMnemonic()}
                  disabled={mnemonicLoading || !mnemonicConcept.trim()}
                  style={{ padding: '10px 22px', display: 'flex', alignItems: 'center', gap: 6 }}
                >
                  {mnemonicLoading ? <RefreshCw size={14} className="animate-spin" /> : <Sparkles size={14} />}
                  {mnemonicLoading ? 'Forging Memory Anchors with Gemini...' : 'Synthesize Memory Anchors & Flashcards'}
                </button>
              </div>
            </div>

            {/* Mnemonic Display */}
            {mnemonicResult && (
              <div className="animate-fade-in">
                {/* Story & Metaphor Cards */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
                  <div className="glass-card" style={{ borderLeft: '4px solid var(--mint-dark)', background: '#ffffff' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                      <h4 style={{ fontSize: 13, fontWeight: 700, textTransform: 'uppercase', color: 'var(--mint-dark)' }}>
                        🎨 Visual / Narrative Mnemonic
                      </h4>
                      <button
                        className="btn-secondary btn-sm"
                        onClick={() => {
                          navigator.clipboard.writeText(mnemonicResult.story_mnemonic);
                          setCopiedMnemonic(true);
                          setTimeout(() => setCopiedMnemonic(false), 2000);
                        }}
                      >
                        {copiedMnemonic ? <CheckCheck size={12} color="var(--mint-dark)" /> : <Copy size={12} />}
                        {copiedMnemonic ? 'Copied' : 'Copy'}
                      </button>
                    </div>
                    <p style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--ink)' }}>
                      {mnemonicResult.story_mnemonic}
                    </p>
                  </div>

                  <div className="glass-card" style={{ borderLeft: '4px solid var(--yellow-dark)', background: '#ffffff' }}>
                    <h4 style={{ fontSize: 13, fontWeight: 700, textTransform: 'uppercase', color: 'var(--yellow-dark)', marginBottom: 10 }}>
                      ⚡ Catchy Acronym / Rhyme
                    </h4>
                    <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--ink)', padding: '12px', background: 'var(--yellow-bg)', borderRadius: 'var(--radius-sm)', marginBottom: 10 }}>
                      "{mnemonicResult.acronym_or_rhyme}"
                    </div>
                    <p style={{ fontSize: 12, color: 'var(--muted)' }}>
                      Repeat this anchor 3 times while visualizing the narrative story above.
                    </p>
                  </div>

                  <div className="glass-card" style={{ borderLeft: '4px solid var(--coral)', background: '#ffffff' }}>
                    <h4 style={{ fontSize: 13, fontWeight: 700, textTransform: 'uppercase', color: 'var(--coral)', marginBottom: 10 }}>
                      🏗️ Real-World Engineering Metaphor
                    </h4>
                    <p style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--ink)' }}>
                      {mnemonicResult.real_world_metaphor}
                    </p>
                  </div>
                </div>

                {/* Interactive Flashcard Section */}
                <div style={{ marginTop: 24 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                    <div>
                      <h3 style={{ fontSize: 16, fontWeight: 800 }}>
                        🎴 Active Recall Flashcards ({mnemonicResult.concept_name})
                      </h3>
                      <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                        Click any card to flip between Question and Answer. Testing forces synaptic reconstruction!
                      </span>
                    </div>
                  </div>

                  <div className="mnemonic-grid">
                    {mnemonicResult.flashcards.map((card, fcIdx) => {
                      const isFlipped = flippedCards[fcIdx];
                      return (
                        <div
                          key={fcIdx}
                          className="flashcard-card"
                          onClick={() => setFlippedCards({ ...flippedCards, [fcIdx]: !isFlipped })}
                        >
                          <div className={`flashcard-inner ${isFlipped ? 'flipped' : ''}`}>
                            {/* Front */}
                            <div className="flashcard-face flashcard-front">
                              <div>
                                <span className="badge badge-medium" style={{ fontSize: 10, marginBottom: 8, display: 'inline-block' }}>
                                  Flashcard {fcIdx + 1}
                                </span>
                                <h4 style={{ fontSize: 14, fontWeight: 700, color: 'var(--ink)', lineHeight: 1.5 }}>
                                  {card.front}
                                </h4>
                              </div>
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11, color: 'var(--muted)' }}>
                                <span>{card.hint ? `💡 Hint: ${card.hint}` : 'Click to flip'}</span>
                                <span style={{ fontWeight: 600, color: 'var(--mint-dark)' }}>Reveal Answer ↻</span>
                              </div>
                            </div>

                            {/* Back */}
                            <div className="flashcard-face flashcard-back">
                              <div>
                                <span className="badge badge-easy" style={{ fontSize: 10, marginBottom: 8, display: 'inline-block' }}>
                                  Answer & Explanation
                                </span>
                                <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--mint-dark)', lineHeight: 1.5 }}>
                                  {card.back}
                                </p>
                              </div>
                              <div style={{ display: 'flex', justifyContent: 'flex-end', fontSize: 11, color: 'var(--mint-dark)', fontWeight: 700 }}>
                                Flip Back ↺
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ================= SCREEN 4: MATERIALS & AI QUESTIONS ================= */}
        {activeTab === 'materials' && (
          <div className="animate-fade-in">
            <div className="section-header">
              <div>
                <h1 className="section-title">
                  <BookOpen size={18} /> Study Materials & Synthesized Questions
                </h1>
                <span className="section-subtitle">
                  Upload raw lecture notes, syllabus excerpts, or textbooks to extract HLR concepts and Gemini AI questions.
                </span>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(300px, 1fr) 2fr', gap: 20, marginTop: 18 }}>
              {/* Left Column: Upload Form */}
              <div className="glass-card" style={{ height: 'fit-content' }}>
                <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 7 }}>
                  <Upload size={15} color="var(--mint-dark)" /> Ingest New Material
                </h3>

                {uploadSuccess && (
                  <div style={{ padding: '9px 12px', borderRadius: 'var(--radius-sm)', background: 'var(--mint-bg)', border: '1px solid #c2e2cf', color: 'var(--mint-dark)', fontSize: 12, marginBottom: 14 }}>
                    ✓ Concept extracted & synthesized questions added to review queue!
                  </div>
                )}

                <form onSubmit={handleMaterialSubmit}>
                  <div className="input-group">
                    <label className="input-label">Subject</label>
                    <select
                      className="select-input"
                      value={materialForm.subject}
                      onChange={e => setMaterialForm({ ...materialForm, subject: e.target.value })}
                    >
                      <option value="Artificial Intelligence">Artificial Intelligence</option>
                      <option value="Operating Systems">Operating Systems</option>
                      <option value="Mathematics">Mathematics</option>
                      <option value="Distributed Systems">Distributed Systems</option>
                    </select>
                  </div>

                  <div className="input-group">
                    <label className="input-label">Topic Area</label>
                    <input
                      type="text"
                      className="text-input"
                      placeholder="e.g. Distributed Consensus"
                      value={materialForm.topic}
                      onChange={e => setMaterialForm({ ...materialForm, topic: e.target.value })}
                    />
                  </div>

                  <div className="input-group">
                    <label className="input-label">Concept Title</label>
                    <input
                      type="text"
                      className="text-input"
                      placeholder="e.g. Raft Log Compaction"
                      value={materialForm.title}
                      onChange={e => setMaterialForm({ ...materialForm, title: e.target.value })}
                    />
                  </div>

                  <div className="input-group">
                    <label className="input-label">Notes Content (Text or Syllabus)</label>
                    <textarea
                      rows={5}
                      className="textarea-input"
                      placeholder="Paste your lecture notes, summaries, or slides..."
                      value={materialForm.content}
                      onChange={e => setMaterialForm({ ...materialForm, content: e.target.value })}
                    />
                  </div>

                  <button
                    type="submit"
                    className="btn-primary"
                    disabled={uploading}
                    style={{ width: '100%', padding: '10px' }}
                  >
                    {uploading ? (
                      <>Synthesizing AI Questions...</>
                    ) : (
                      <><Sparkles size={14} /> Process & Generate Questions</>
                    )}
                  </button>
                </form>
              </div>

              {/* Right Column: Question Review Queue */}
              <div>
                <div className="glass-card" style={{ marginBottom: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
                    <div>
                      <h3 style={{ fontSize: 15, fontWeight: 700 }}>Question Review & Moderation</h3>
                      <p style={{ fontSize: 12, color: 'var(--muted)' }}>
                        Quality questions protect the HLR model parameter signal. Approve or flag generated items.
                      </p>
                    </div>

                    <div style={{ display: 'flex', gap: 4 }}>
                      {['all', 'approved', 'draft', 'flagged'].map(filter => (
                        <button
                          key={filter}
                          className={`nav-tab-btn ${questionFilter === filter ? 'active' : ''}`}
                          onClick={() => setQuestionFilter(filter)}
                          style={{ padding: '5px 10px', fontSize: 11 }}
                        >
                          {filter.toUpperCase()}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  {filteredQuestions.map(q => (
                    <div key={q.id} className="glass-card">
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                          <span className="badge badge-medium">{q.concept_name}</span>
                          <span style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>{q.subject}</span>
                        </div>
                        <div>
                          {q.status === 'approved' && (
                            <span className="badge badge-easy"><Check size={11} /> Approved</span>
                          )}
                          {q.status === 'draft' && (
                            <span className="badge badge-medium">Draft</span>
                          )}
                          {q.status === 'flagged' && (
                            <span className="badge badge-due"><Flag size={11} /> Flagged</span>
                          )}
                        </div>
                      </div>

                      <p style={{ fontSize: 14, fontWeight: 700, color: 'var(--ink)', marginBottom: 14 }}>
                        {q.text}
                      </p>

                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14 }}>
                        {q.options.map((opt, oIdx) => (
                          <div
                            key={oIdx}
                            style={{
                              padding: '8px 12px',
                              borderRadius: 'var(--radius-sm)',
                              background: oIdx === q.answer_index ? 'var(--mint-bg)' : '#ffffff',
                              border: oIdx === q.answer_index ? '1px solid #c2e2cf' : '1px solid var(--line)',
                              fontSize: 12,
                              color: oIdx === q.answer_index ? 'var(--mint-dark)' : 'var(--ink)',
                              fontWeight: oIdx === q.answer_index ? 600 : 400
                            }}
                          >
                            <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, marginRight: 6 }}>
                              {['A', 'B', 'C', 'D'][oIdx]}:
                            </span>
                            {opt}
                          </div>
                        ))}
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: 10, borderTop: '1px solid var(--line)' }}>
                        <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--muted)' }}>
                          ID: {q.id}
                        </span>
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button
                            className="btn-danger btn-sm"
                            onClick={() => handleQuestionStatus(q.id, 'flagged')}
                          >
                            <Flag size={12} /> Flag
                          </button>
                          <button
                            className="btn-success btn-sm"
                            onClick={() => handleQuestionStatus(q.id, 'approved')}
                          >
                            <Check size={12} /> Approve
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ================= SCREEN 5: FORGETTING CURVE ================= */}
        {activeTab === 'curve' && (
          <div className="animate-fade-in">
            <div className="section-header">
              <div>
                <h1 className="section-title">
                  <LineChart size={18} /> Concept Detail & Forgetting Curve
                </h1>
                <span className="section-subtitle">
                  Empirical half-life model visualization based on Settles & Meeder (2016) Figure 4.
                </span>
              </div>
              <div>
                <select
                  className="select-input"
                  style={{ minWidth: 260 }}
                  value={selectedConceptId}
                  onChange={e => setSelectedConceptId(e.target.value)}
                >
                  {concepts.map(c => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.subject})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {curveData && (
              <div style={{ marginTop: 20 }}>
                {/* Concept Metrics Bar */}
                <div className="metrics-grid" style={{ marginBottom: 18 }}>
                  <div className="glass-card" style={{ padding: 16 }}>
                    <div className="metric-label">Estimated Half-Life (ĥ)</div>
                    <div className="metric-value" style={{ color: 'var(--mint-dark)' }}>
                      {curveData.half_life_days} <span style={{ fontSize: 15, color: 'var(--muted)' }}>days</span>
                    </div>
                    <div className="metric-sub">Time until recall drops to 50%</div>
                  </div>

                  <div className="glass-card" style={{ padding: 16 }}>
                    <div className="metric-label">Current Recall (p̂)</div>
                    <div className="metric-value" style={{ color: curveData.current_p_hat <= 0.70 ? 'var(--coral)' : 'var(--mint-dark)' }}>
                      {(curveData.current_p_hat * 100).toFixed(1)}%
                    </div>
                    <div className="metric-sub">Elapsed: {curveData.current_delta_days} days</div>
                  </div>

                  <div className="glass-card" style={{ padding: 16 }}>
                    <div className="metric-label">Practice History</div>
                    <div className="metric-value">
                      <span style={{ color: 'var(--mint-dark)' }}>{curveData.concept.n_right}</span>
                      <span style={{ color: 'var(--muted)', margin: '0 5px' }}>/</span>
                      <span style={{ color: 'var(--coral)' }}>{curveData.concept.n_wrong}</span>
                    </div>
                    <div className="metric-sub">Correct / Missed</div>
                  </div>

                  <div className="glass-card" style={{ padding: 16, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                    <button
                      className="btn-primary"
                      onClick={() => startQuizSession(null, curveData.concept.id)}
                      style={{ width: '100%' }}
                    >
                      <Play size={14} /> Practice Concept
                    </button>
                  </div>
                </div>

                {/* High-Precision SVG Forgetting Curve Chart (Figure 4) */}
                {(() => {
                  const pts = curveData.curve_points || [];
                  const lastD = pts.length ? pts[pts.length - 1].delta_days : 12;
                  const maxD = Math.max(10, Math.ceil(lastD / 2) * 2);

                  const padL = 65;
                  const padR = 40;
                  const padT = 35;
                  const padB = 60;
                  const w = 840;
                  const h = 340;
                  const plotW = w - padL - padR;
                  const plotH = h - padT - padB;

                  const toX = (days) => padL + (Math.max(0, days) / maxD) * plotW;
                  const toY = (prob) => padT + (1.0 - Math.min(1.0, Math.max(0, prob))) * plotH;

                  const curveCoords = pts.map(pt => `${toX(pt.delta_days).toFixed(1)},${toY(pt.p_hat).toFixed(1)}`);
                  const dPath = pts.length ? `M ${curveCoords.join(' L ')}` : '';
                  const areaPath = pts.length ? `M ${curveCoords[0]} L ${curveCoords.join(' L ')} L ${toX(lastD).toFixed(1)},${(padT + plotH).toFixed(1)} L ${toX(0).toFixed(1)},${(padT + plotH).toFixed(1)} Z` : '';

                  // Simulation scrubber coordinates
                  const simP = calcRecallProb(curveData.half_life_days, simulatedDelta);
                  const simX = toX(simulatedDelta);
                  const simY = toY(simP);

                  // Today marker coordinates
                  const todayD = curveData.current_delta_days;
                  const todayP = curveData.current_p_hat;
                  const todayX = toX(todayD);
                  const todayY = toY(todayP);

                  // Nice X-axis ticks (e.g. 0, 2, 4, 6, 8, ... maxD)
                  const xTickCount = Math.min(7, Math.max(4, Math.floor(maxD / 2)));
                  const xStep = Math.max(1, Math.round(maxD / xTickCount));
                  const xTicks = [];
                  for (let d = 0; d <= maxD; d += xStep) {
                    xTicks.push(d);
                  }
                  if (xTicks[xTicks.length - 1] !== maxD) {
                    xTicks.push(maxD);
                  }

                  // Y ticks
                  const yTicks = [1.0, 0.75, 0.70, 0.50, 0.25, 0.0];

                  return (
                    <div className="glass-card" style={{ padding: 24 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 10 }}>
                        <div>
                          <h3 style={{ fontSize: 16, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 7, color: 'var(--ink)' }}>
                            <TrendingDown size={16} color="var(--mint-dark)" /> Empirical Forgetting Curve: p̂(Δ) = 2^(-Δ / ĥ)
                          </h3>
                          <span style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
                            Settles & Meeder (2016) Figure 4 formulation with target threshold and observed review events
                          </span>
                        </div>
                        <div style={{ display: 'flex', gap: 16, fontSize: 11, fontFamily: 'var(--font-mono)' }}>
                          <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: 'var(--mint-dark)' }}>
                            <span style={{ width: 14, height: 3, background: 'var(--mint-dark)', borderRadius: 2 }}></span> HLR Curve
                          </span>
                          <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: 'var(--coral)' }}>
                            <span style={{ width: 14, height: 0, borderTop: '2px dashed var(--coral)' }}></span> Threshold (0.70)
                          </span>
                          <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: 'var(--ink)' }}>
                            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#ffffff', border: '2px solid var(--mint-dark)' }}></span> Practice Points
                          </span>
                          <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: 'var(--coral)' }}>
                            <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--coral)' }}></span> Today
                          </span>
                        </div>
                      </div>

                      {/* SVG Canvas */}
                      <div className="chart-container" style={{ position: 'relative' }}>
                        <svg className="chart-svg" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
                          <defs>
                            <linearGradient id="paperCurveGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                              <stop offset="0%" stopColor="#a5d5bf" stopOpacity="0.45" />
                              <stop offset="100%" stopColor="#a5d5bf" stopOpacity="0.03" />
                            </linearGradient>
                          </defs>

                          {/* Y-Axis Label */}
                          <text x={padL - 10} y={padT - 14} fill="var(--muted)" fontSize="10" fontWeight="600" textAnchor="end" fontFamily="var(--font-mono)">
                            RECALL p̂
                          </text>

                          {/* Horizontal Grid & Ticks */}
                          {yTicks.map((prob, i) => {
                            const y = toY(prob);
                            const isThreshold = prob === 0.70;
                            return (
                              <g key={i}>
                                <line
                                  x1={padL}
                                  y1={y}
                                  x2={padL + plotW}
                                  y2={y}
                                  stroke={isThreshold ? 'var(--coral)' : '#e8e6dd'}
                                  strokeDasharray={isThreshold ? '5,4' : 'none'}
                                  strokeWidth={isThreshold ? 1.5 : 1}
                                />
                                <text
                                  x={padL - 10}
                                  y={y + 4}
                                  fill={isThreshold ? 'var(--coral)' : 'var(--muted)'}
                                  fontSize="11"
                                  fontWeight={isThreshold ? 700 : 400}
                                  fontFamily="var(--font-mono)"
                                  textAnchor="end"
                                >
                                  {Math.round(prob * 100)}%
                                </text>
                                {isThreshold && (
                                  <text
                                    x={padL + plotW - 6}
                                    y={y - 6}
                                    fill="var(--coral)"
                                    fontSize="10"
                                    fontWeight="600"
                                    fontFamily="var(--font-mono)"
                                    textAnchor="end"
                                  >
                                    Target Review Threshold (0.70)
                                  </text>
                                )}
                              </g>
                            );
                          })}

                          {/* X-Axis Solid Base Line */}
                          <line
                            x1={padL}
                            y1={padT + plotH}
                            x2={padL + plotW}
                            y2={padT + plotH}
                            stroke="#cfccc0"
                            strokeWidth="1.5"
                          />

                          {/* X Ticks & Labels */}
                          {xTicks.map((d, i) => {
                            const x = toX(d);
                            return (
                              <g key={i}>
                                <line
                                  x1={x}
                                  y1={padT + plotH}
                                  x2={x}
                                  y2={padT + plotH + 5}
                                  stroke="#cfccc0"
                                  strokeWidth="1.5"
                                />
                                <text
                                  x={x}
                                  y={padT + plotH + 18}
                                  fill="var(--muted)"
                                  fontSize="11"
                                  fontFamily="var(--font-mono)"
                                  textAnchor="middle"
                                >
                                  {d}d
                                </text>
                              </g>
                            );
                          })}

                          {/* X-Axis Title */}
                          <text
                            x={padL + plotW / 2}
                            y={h - 12}
                            fill="var(--muted)"
                            fontSize="11"
                            fontFamily="var(--font-mono)"
                            textAnchor="middle"
                          >
                            Elapsed Time Since Last Review Δ (Days)
                          </text>

                          {/* Curve Shading & Stroke */}
                          {areaPath && <path d={areaPath} fill="url(#paperCurveGradient)" />}
                          {dPath && <path d={dPath} fill="none" stroke="var(--mint-dark)" strokeWidth="3" strokeLinecap="round" />}

                          {/* Interactive Simulation Scrubber (linked directly to slider) */}
                          <g>
                            <line
                              x1={simX}
                              y1={padT}
                              x2={simX}
                              y2={padT + plotH}
                              stroke="var(--mint-dark)"
                              strokeDasharray="3,3"
                              strokeWidth="1.5"
                              opacity="0.6"
                            />
                            <circle cx={simX} cy={simY} r="7" fill="#ffffff" stroke="var(--mint-dark)" strokeWidth="2.5" />
                            <circle cx={simX} cy={simY} r="3" fill="var(--mint-dark)" />
                            
                            {/* Scrubber Badge */}
                            <g transform={`translate(${Math.min(padL + plotW - 90, Math.max(padL + 10, simX - 45))}, ${Math.max(padT + 5, simY - 32)})`}>
                              <rect x="0" y="0" width="90" height="22" rx="3" fill="var(--ink)" />
                              <text x="45" y="15" fill="#ffffff" fontSize="10" fontWeight="600" textAnchor="middle" fontFamily="var(--font-mono)">
                                Δ={simulatedDelta}d : {Math.round(simP * 100)}%
                              </text>
                            </g>
                          </g>

                          {/* Today Position Marker (Clean Pin, zero collision) */}
                          <g>
                            <line
                              x1={todayX}
                              y1={todayY}
                              x2={todayX}
                              y2={padT + plotH}
                              stroke="var(--coral)"
                              strokeDasharray="2,2"
                              strokeWidth="1.5"
                            />
                            <circle cx={todayX} cy={todayY} r="7" fill="var(--coral-bg)" stroke="var(--coral)" strokeWidth="2" />
                            <circle cx={todayX} cy={todayY} r="3" fill="var(--coral)" />
                            {/* Today Pill at Axis */}
                            <g transform={`translate(${Math.min(padL + plotW - 60, Math.max(padL, todayX - 30))}, ${padT + plotH + 24})`}>
                              <rect x="0" y="0" width="60" height="18" rx="2" fill="var(--coral)" />
                              <text x="30" y="12" fill="#ffffff" fontSize="9" fontWeight="700" textAnchor="middle" fontFamily="var(--font-mono)">
                                TODAY
                              </text>
                            </g>
                          </g>

                          {/* Practice Scatter Points (Interactive with hover, NO static text collisions) */}
                          {curveData.practice_points?.map((pt, pIdx) => {
                            const cx = toX(pt.delta_days);
                            const cy = toY(pt.p_observed);
                            const isHovered = hoveredPoint?.index === pIdx;
                            return (
                              <g
                                key={pIdx}
                                style={{ cursor: 'pointer' }}
                                onMouseEnter={() => setHoveredPoint({
                                  index: pIdx,
                                  x: cx,
                                  y: cy,
                                  title: pt.type,
                                  score: `${Math.round(pt.p_observed * 100)}%`,
                                  delta: `${pt.delta_days} days ago`,
                                  date: pt.date
                                })}
                                onMouseLeave={() => setHoveredPoint(null)}
                              >
                                {/* Wide touch/hover hit zone */}
                                <circle cx={cx} cy={cy} r="16" fill="transparent" />
                                <circle cx={cx} cy={cy} r={isHovered ? 8 : 6} fill="#ffffff" stroke="var(--mint-dark)" strokeWidth={isHovered ? 3 : 2} />
                                <circle cx={cx} cy={cy} r="2.5" fill="var(--mint-dark)" />
                              </g>
                            );
                          })}

                          {/* Interactive Floating Hover Tooltip */}
                          {hoveredPoint && (
                            <g transform={`translate(${Math.min(padL + plotW - 140, Math.max(padL, hoveredPoint.x - 70))}, ${Math.max(padT, hoveredPoint.y - 65)})`}>
                              <rect x="0" y="0" width="140" height="54" rx="4" fill="#ffffff" stroke="var(--line)" filter="drop-shadow(0 2px 5px rgba(0,0,0,0.1))" />
                              <text x="10" y="18" fill="var(--ink)" fontSize="11" fontWeight="700">
                                {hoveredPoint.title}
                              </text>
                              <text x="10" y="34" fill="var(--mint-dark)" fontSize="11" fontWeight="600" fontFamily="var(--font-mono)">
                                Recall: {hoveredPoint.score}
                              </text>
                              <text x="10" y="46" fill="var(--muted)" fontSize="9" fontFamily="var(--font-mono)">
                                {hoveredPoint.delta} • {hoveredPoint.date}
                              </text>
                            </g>
                          )}
                        </svg>
                      </div>

                      {/* Interactive Elapsed Time Simulator */}
                      <div className="interactive-slider-box">
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)' }}>
                            <Sliders size={14} style={{ verticalAlign: 'middle', marginRight: 5 }} /> Interactive Elapsed Time Simulation (Δ Days)
                          </span>
                          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--mint-dark)' }}>
                            Δ = {simulatedDelta} days → Projected Recall: <b>{Math.round(calcRecallProb(curveData.half_life_days, simulatedDelta) * 100)}%</b>
                          </span>
                        </div>

                        <input
                          type="range"
                          min="0"
                          max={maxD}
                          step="0.1"
                          className="range-input"
                          value={simulatedDelta}
                          onChange={e => setSimulatedDelta(parseFloat(e.target.value))}
                        />

                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--muted)', marginTop: 6 }}>
                          <span>0 days (100% immediate recall)</span>
                          <span>ĥ = {curveData.half_life_days}d (50% retention mark)</span>
                          <span>{maxD} days</span>
                        </div>
                      </div>

                      {/* Clean Observed Practice Event Log Cards */}
                      {curveData.practice_points?.length > 0 && (
                        <div style={{ marginTop: 20 }}>
                          <h4 style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 10 }}>
                            Observed Practice Review Checkpoints
                          </h4>
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 10 }}>
                            {curveData.practice_points.map((pt, pIdx) => (
                              <div
                                key={pIdx}
                                style={{
                                  padding: '10px 14px',
                                  borderRadius: 'var(--radius-sm)',
                                  background: '#f8f6f0',
                                  border: '1px solid var(--line)',
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'space-between'
                                }}
                              >
                                <div>
                                  <div style={{ fontWeight: 700, fontSize: 12, color: 'var(--ink)' }}>{pt.type}</div>
                                  <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--muted)', marginTop: 2 }}>
                                    Δ = {pt.delta_days}d • {pt.date}
                                  </div>
                                </div>
                                <span
                                  className="badge"
                                  style={{
                                    background: pt.p_observed >= 0.8 ? 'var(--mint-bg)' : pt.p_observed >= 0.7 ? 'var(--yellow-bg)' : 'var(--coral-bg)',
                                    color: pt.p_observed >= 0.8 ? 'var(--mint-dark)' : pt.p_observed >= 0.7 ? 'var(--yellow-dark)' : 'var(--coral-dark)',
                                    border: '1px solid currentColor'
                                  }}
                                >
                                  {Math.round(pt.p_observed * 100)}%
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Math Parameter Breakdown */}
                      <div style={{ marginTop: 18, padding: 16, borderRadius: 'var(--radius-sm)', background: '#f7f4ed', border: '1px solid var(--line)' }}>
                        <h4 style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 8 }}>
                          HLR Model Mathematical Parameter Breakdown
                        </h4>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10, fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                          <div>
                            <span style={{ color: 'var(--muted)' }}>Vector Θ: </span>
                            <span>[θ0=0.0, θ_r=+1.0, θ_w=-1.0]</span>
                          </div>
                          <div>
                            <span style={{ color: 'var(--muted)' }}>Vector X: </span>
                            <span>[1, right={curveData.concept.n_right}, wrong={curveData.concept.n_wrong}]</span>
                          </div>
                          <div>
                            <span style={{ color: 'var(--muted)' }}>Dot Product: </span>
                            <span>Θ · X = {(curveData.concept.n_right - curveData.concept.n_wrong).toFixed(1)}</span>
                          </div>
                          <div>
                            <span style={{ color: 'var(--muted)' }}>ĥ = 2^(Θ·X): </span>
                            <span style={{ color: 'var(--mint-dark)', fontWeight: 700 }}>{curveData.half_life_days} days</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })()}
              </div>
            )}
          </div>
        )}

        {/* ================= SCREEN 6: SETTINGS & MODEL SPEC ================= */}
        {activeTab === 'settings' && (
          <div className="animate-fade-in" style={{ maxWidth: 840, margin: '0 auto' }}>
            <div className="section-header">
              <div>
                <h1 className="section-title">
                  <Settings size={18} /> Planner Settings & HLR Model Engine
                </h1>
                <span className="section-subtitle">
                  Configure study preferences, exam deadlines, and inspect machine learning model versions.
                </span>
              </div>
            </div>

            <div className="glass-card" style={{ marginTop: 20, marginBottom: 20 }}>
              <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 16 }}>
                Study Time & Target Retention
              </h3>

              <div className="input-group">
                <label className="input-label">Daily Study Time Budget</label>
                <div style={{ display: 'flex', gap: 8 }}>
                  {[15, 30, 45, 60, 90].map(mins => (
                    <button
                      key={mins}
                      className={`btn-secondary ${settings.daily_minutes === mins ? 'btn-primary' : ''}`}
                      onClick={() => setSettings({ ...settings, daily_minutes: mins })}
                      style={{ flex: 1 }}
                    >
                      {mins} mins
                    </button>
                  ))}
                </div>
              </div>

              <div className="input-group" style={{ marginTop: 16 }}>
                <label className="input-label">
                  Target Retention Threshold: <b>{Math.round(settings.retention_threshold * 100)}%</b>
                </label>
                <input
                  type="range"
                  min="0.50"
                  max="0.90"
                  step="0.05"
                  className="range-input"
                  value={settings.retention_threshold}
                  onChange={e => setSettings({ ...settings, retention_threshold: parseFloat(e.target.value) })}
                />
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--muted)' }}>
                  When recall falls below this threshold, concepts are flagged as due for scheduling.
                </span>
              </div>
            </div>

            <div className="glass-card" style={{ marginBottom: 20 }}>
              <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 16 }}>
                Subject Exam Deadlines
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 14 }}>
                {Object.keys(settings.exam_dates).map(subj => (
                  <div key={subj} className="input-group">
                    <label className="input-label">{subj}</label>
                    <input
                      type="date"
                      className="text-input"
                      value={settings.exam_dates[subj]}
                      onChange={e => {
                        const updated = { ...settings.exam_dates, [subj]: e.target.value };
                        setSettings({ ...settings, exam_dates: updated });
                      }}
                    />
                  </div>
                ))}
              </div>
            </div>

            <div className="glass-card">
              <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 7 }}>
                <Database size={15} color="var(--mint-dark)" /> HLR Model Versions & Feature Specs
              </h3>
              <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 16 }}>
                The launch model uses raw counts (Leitner weights: correct doubles half-life, wrong halves it). The trained model uses √counts as in Settles & Meeder (2016).
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div style={{ padding: 14, borderRadius: 'var(--radius-sm)', background: 'var(--mint-bg)', border: '1px solid #c2e2cf' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 700, color: 'var(--ink)' }}>Launch Model (Raw Counts)</span>
                    <span className="badge badge-easy">ACTIVE</span>
                  </div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--mint-dark)', marginTop: 4 }}>
                    Feature Spec: x = [1, n_right, n_wrong] | Weights Θ = [0.0, 1.0, -1.0]
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
                    Correct answer multiplies ĥ by 2; incorrect answer halves ĥ.
                  </div>
                </div>

                <div style={{ padding: 14, borderRadius: 'var(--radius-sm)', background: '#f0ede6', border: '1px solid var(--line)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 700, color: 'var(--muted)' }}>Trained Model (√Counts - Settles & Meeder)</span>
                    <span className="badge badge-medium">STAGING</span>
                  </div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>
                    Feature Spec: x = [1, √n_right, √n_wrong] | Weights Θ = [0.15, 1.42, -1.18]
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
                    Learned via AdaGrad offline gradient descent on student attempt logs.
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ================= MODAL: ONBOARDING WIZARD ================= */}
        {showOnboarding && (
          <div
            style={{
              position: 'fixed',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: 'rgba(36, 49, 46, 0.4)',
              backdropFilter: 'blur(4px)',
              zIndex: 100,
              display: 'grid',
              placeItems: 'center',
              padding: 20
            }}
          >
            <div className="glass-card animate-fade-in" style={{ maxWidth: 520, width: '100%', padding: 28, background: '#ffffff' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                <h3 style={{ fontSize: 17, fontWeight: 800 }}>FocusFlow Setup Wizard</h3>
                <button onClick={() => setShowOnboarding(false)} style={{ color: 'var(--muted)' }}>
                  <X size={18} />
                </button>
              </div>

              <p style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 18 }}>
                Configure your target subjects and study capacity to initialize your personal HLR memory model.
              </p>

              <div className="input-group">
                <label className="input-label">Daily Available Study Time</label>
                <div style={{ display: 'flex', gap: 6 }}>
                  {[20, 30, 45, 60].map(mins => (
                    <button
                      key={mins}
                      className={`btn-secondary ${settings.daily_minutes === mins ? 'btn-primary' : ''}`}
                      onClick={() => setSettings({ ...settings, daily_minutes: mins })}
                      style={{ flex: 1, padding: 7 }}
                    >
                      {mins}m
                    </button>
                  ))}
                </div>
              </div>

              <div className="input-group">
                <label className="input-label">Subjects to Track</label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {Object.keys(settings.subject_priorities).map(subj => (
                    <span key={subj} className="badge badge-easy" style={{ padding: '5px 10px', fontSize: 11 }}>
                      <Check size={12} /> {subj}
                    </span>
                  ))}
                </div>
              </div>

              <div style={{ marginTop: 22, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                <button className="btn-secondary" onClick={() => setShowOnboarding(false)}>
                  Close
                </button>
                <button
                  className="btn-primary"
                  onClick={() => {
                    setShowOnboarding(false);
                    setActiveTab('plan');
                  }}
                >
                  Generate Adaptive Plan
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

const container = document.getElementById('root');
if (container) {
  const root = createRoot(container);
  root.render(<App />);
}
