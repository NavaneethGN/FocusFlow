import React, { useState, useEffect, useMemo, useRef } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Brain,
  BookOpen,
  Calendar,
  CheckCircle2,
  Clock,
  Compass,
  FileText,
  File,
  FileUp,
  FileCheck,
  Paperclip,
  Trash2,
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
  ArrowUp,
  ArrowDown,
  Check,
  X,
  Plus,
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
  RefreshCw,
  Eye,
  EyeOff,
  Save,
  Key,
  ShieldCheck
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

function createDefaultConceptsMessage(subject, allConcepts = [], allMaterials = []) {
  const subjConcepts = allConcepts.filter(c => subject === 'All' || c.subject.toLowerCase() === subject.toLowerCase());
  const subjMaterials = allMaterials.filter(m => subject === 'All' || m.subject.toLowerCase() === subject.toLowerCase());

  let bulletPoints = [];
  if (subjConcepts.length > 0) {
    bulletPoints = subjConcepts.slice(0, 5).map(c => {
      const topicTag = c.topic ? ` (${c.topic})` : '';
      return `• **${c.name}**${topicTag}: Key invariant with estimated recall ${(c.p_hat * 100).toFixed(0)}% and memory half-life of ${c.half_life_days}d.`;
    });
  } else if (subjMaterials.length > 0) {
    bulletPoints = subjMaterials.slice(0, 4).map(m => `• **${m.title}**: ${m.content.slice(0, 140)}...`);
  } else {
    bulletPoints = [
      `• **Foundational Principles**: Core theorems and systemic models.`,
      `• **State Invariants**: Ensuring fault-tolerant execution boundaries.`,
      `• **Active Recall Memory Curve**: Calibrated by the Settles & Meeder (2016) HLR engine.`
    ];
  }

  const subjectTitle = subject === 'All' ? 'All Subjects' : subject;

  return {
    role: 'model',
    content: `Hello! I am your **FocusFlow AI Study Tutor & Doubt Solver**, grounded directly in your **${subjectTitle}** study sources on the left sidebar.\n\n### Main Concepts of ${subjectTitle}:\n${bulletPoints.join('\n')}\n\nAsk me any doubt about these concepts or your uploaded documents, or add new PDFs/DOCX/PPTs in the left sidebar!`,
    timestamp: 'Just now',
    followups: subjConcepts.length >= 2 ? [
      `Explain ${subjConcepts[0].name} in simple terms`,
      `What are the common exam pitfalls in ${subjConcepts[1].name}?`,
      `Quiz me on ${subjectTitle}`
    ] : [
      `Explain the core mechanism from my notes`,
      `What are the most common exam traps in ${subjectTitle}?`,
      `Quiz me on ${subjectTitle}`
    ],
    cited_materials: subjMaterials.map(m => m.title).slice(0, 3),
    aiPowered: false
  };
}

// ---------------------------------------------------------------------------
// Chatbot Rich Text Renderer: Bold headings, bullet lists, highlighted text
// ---------------------------------------------------------------------------
function formatInlineText(text) {
  if (!text) return text;
  const parts = [];
  const regex = /(`[^`]+`|\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*)/g;
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.substring(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith('`') && token.endsWith('`')) {
      parts.push(
        <code
          key={match.index}
          style={{
            background: 'rgba(50, 96, 78, 0.08)',
            padding: '2px 5px',
            borderRadius: 4,
            fontFamily: 'var(--font-mono)',
            fontSize: '0.9em',
            fontWeight: 700,
            color: 'var(--mint-dark)'
          }}
        >
          {token.slice(1, -1)}
        </code>
      );
    } else if ((token.startsWith('**') && token.endsWith('**')) || (token.startsWith('__') && token.endsWith('__'))) {
      parts.push(
        <strong
          key={match.index}
          style={{
            fontWeight: 850,
            color: 'inherit'
          }}
        >
          {token.slice(2, -2)}
        </strong>
      );
    } else if (token.startsWith('*') && token.endsWith('*')) {
      parts.push(<em key={match.index}>{token.slice(1, -1)}</em>);
    }
    lastIndex = match.index + token.length;
  }
  if (lastIndex < text.length) {
    parts.push(text.substring(lastIndex));
  }
  return parts.length > 0 ? parts : text;
}

function RenderFormattedChatMessage({ content }) {
  if (!content) return null;
  const lines = content.split('\n');

  return (
    <div className="chat-formatted-body">
      {lines.map((line, idx) => {
        const trimmed = line.trim();
        if (!trimmed) {
          return <div key={idx} style={{ height: 6 }} />;
        }

        // Headings: use bold for headings and prominent hierarchy
        if (trimmed.startsWith('### ')) {
          return (
            <div
              key={idx}
              style={{
                fontWeight: 850,
                fontSize: '1.05rem',
                marginTop: idx > 0 ? 10 : 2,
                marginBottom: 4,
                letterSpacing: '-0.01em'
              }}
            >
              {formatInlineText(trimmed.replace(/^###\s+/, ''))}
            </div>
          );
        }
        if (trimmed.startsWith('## ')) {
          return (
            <div
              key={idx}
              style={{
                fontWeight: 850,
                fontSize: '1.15rem',
                marginTop: idx > 0 ? 12 : 2,
                marginBottom: 4,
                letterSpacing: '-0.01em'
              }}
            >
              {formatInlineText(trimmed.replace(/^##\s+/, ''))}
            </div>
          );
        }
        if (trimmed.startsWith('# ')) {
          return (
            <div
              key={idx}
              style={{
                fontWeight: 850,
                fontSize: '1.25rem',
                marginTop: idx > 0 ? 14 : 2,
                marginBottom: 6,
                letterSpacing: '-0.02em'
              }}
            >
              {formatInlineText(trimmed.replace(/^#\s+/, ''))}
            </div>
          );
        }

        // Blockquotes
        if (trimmed.startsWith('> ')) {
          return (
            <blockquote
              key={idx}
              style={{
                borderLeft: '3px solid var(--mint-dark)',
                paddingLeft: 10,
                margin: '4px 0',
                color: 'var(--muted)',
                fontStyle: 'italic'
              }}
            >
              {formatInlineText(trimmed.replace(/^>\s+/, ''))}
            </blockquote>
          );
        }

        // Bullet lists
        if (trimmed.startsWith('- ') || trimmed.startsWith('* ') || trimmed.startsWith('• ')) {
          return (
            <div
              key={idx}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 7,
                margin: '2px 0 2px 8px'
              }}
            >
              <span style={{ color: 'var(--mint-dark)', fontWeight: 800, fontSize: '0.9em', marginTop: 1 }}>•</span>
              <div style={{ flex: 1 }}>{formatInlineText(trimmed.replace(/^[-*•]\s+/, ''))}</div>
            </div>
          );
        }

        // Standard paragraph line
        return (
          <div key={idx} style={{ margin: '2px 0' }}>
            {formatInlineText(line)}
          </div>
        );
      })}
    </div>
  );
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

  const [weekPlan, setWeekPlan] = useState(null);
  const [subjectsDetails, setSubjectsDetails] = useState([]);
  const [geminiKeyInput, setGeminiKeyInput] = useState('');
  const [geminiStatus, setGeminiStatus] = useState({ configured: false, healthy: false, model: null, message: '' });
  const [geminiTesting, setGeminiTesting] = useState(false);
  const [showGeminiKey, setShowGeminiKey] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsSavedToast, setSettingsSavedToast] = useState(false);
  const [newSubjectColor, setNewSubjectColor] = useState('#32604e');
  const [newSubjectPriority, setNewSubjectPriority] = useState(1.2);

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

  const [uploadedMaterials, setUploadedMaterials] = useState([
    {
      id: "mat-ai-1",
      subject: "Artificial Intelligence",
      topic: "Deep Learning",
      title: "Transformer Attention Mechanisms & Scaling",
      content: "Scaled dot-product attention computes Attention(Q, K, V) = softmax(QK^T / sqrt(d_k))V. Multi-head attention projects queries, keys, and values h times with learned linear projections to jointly attend to information at different subspaces. Scaling by 1/sqrt(d_k) prevents variance explosion that pushes softmax into regions with vanishing gradients."
    },
    {
      id: "mat-os-1",
      subject: "Operating Systems",
      topic: "Virtual Memory & Concurrency",
      title: "Virtual Memory Paging and Deadlock Conditions",
      content: "Clock (Second-Chance) page replacement uses a circular list and a reference bit. When a page fault occurs, if the pointed page has use bit = 1, it resets it to 0 and advances; if 0, it selects it for eviction. The four necessary Coffman deadlock conditions are: 1) Mutual Exclusion, 2) Hold and Wait, 3) No Preemption (resources cannot be forcibly confiscated), 4) Circular Wait. Breaking any single condition prevents deadlock."
    },
    {
      id: "mat-math-1",
      subject: "Mathematics",
      topic: "Linear Algebra & Probability",
      title: "Eigenvalues & Bayes Theorem",
      content: "Eigenvalues lambda satisfy Av = lambda v, where det(A - lambda I) = 0. Eigendecomposition factorizes A = Q Lambda Q^(-1). Bayes theorem states P(H|E) = [P(E|H) * P(H)] / P(E), updating prior belief P(H) with likelihood P(E|H) to find posterior probability P(H|E)."
    },
    {
      id: "mat-ds-1",
      subject: "Distributed Systems",
      topic: "Consensus & Tradeoffs",
      title: "Raft Consensus and PACELC Theorem",
      content: "Raft divides time into terms. A leader broadcasts heartbeats (AppendEntries). If a candidate or leader receives a higher term from an RPC, it reverts to follower state. PACELC theorem extends CAP: In a partitioned network, choose Availability or Consistency (A vs C); else (E), choose Latency or Consistency (L vs C)."
    }
  ]);

  const [materialForm, setMaterialForm] = useState({
    subject: 'Operating Systems',
    topic: 'Virtual Memory',
    title: 'Page Replacement & Deadlock Rules',
    content: ''
  });
  const [uploading, setUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [questionFilter, setQuestionFilter] = useState('all');

  const [simulatedDelta, setSimulatedDelta] = useState(2.5);

  // File Upload / Paste & Chatbot State
  const fileInputRef = useRef(null);
  const [stagedFiles, setStagedFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [showQuizConfirm, setShowQuizConfirm] = useState(false);
  const [showMaterialsModal, setShowMaterialsModal] = useState(false);
  const [extractingFile, setExtractingFile] = useState(false);

  // NotebookLM Left Sidebar State
  const sidebarFileInputRef = useRef(null);
  const [sidebarUploadTitle, setSidebarUploadTitle] = useState('');
  const [sidebarUploadContent, setSidebarUploadContent] = useState('');
  const [sidebarStagedFiles, setSidebarStagedFiles] = useState([]);
  const [sidebarExtracting, setSidebarExtracting] = useState(false);
  const [sidebarUploading, setSidebarUploading] = useState(false);
  const [sidebarUploadSuccess, setSidebarUploadSuccess] = useState(false);
  const [sidebarDragging, setSidebarDragging] = useState(false);
  const [selectedSourcePreview, setSelectedSourcePreview] = useState(null);

  // ---------------------------------------------------------------------------
  // Adaptive Study Schedule & Slicing State (Session Length Modes, Windows, Slicing)
  // ---------------------------------------------------------------------------
  const [sessionLengthMode, setSessionLengthMode] = useState('ai_optimized'); // 'ai_optimized' | 'manual'
  const [initialSessionDuration, setInitialSessionDuration] = useState(30); // Baseline length: 20 | 30 | 45
  const [sessionDuration, setSessionDuration] = useState(30); // Manual selection: 20 | 30 | 45
  const [freeTimeWindows, setFreeTimeWindows] = useState([
    { id: 'win-1', start: '07:00', end: '08:30', label: 'Morning Focus' },
    { id: 'win-2', start: '20:00', end: '22:00', label: 'Evening Review' }
  ]);
  const [newWindowStart, setNewWindowStart] = useState('14:00');
  const [newWindowEnd, setNewWindowEnd] = useState('15:30');
  const [newWindowLabel, setNewWindowLabel] = useState('Afternoon Deep Work');
  const [showAddWindow, setShowAddWindow] = useState(false);
  const [completedTileIds, setCompletedTileIds] = useState(new Set());
  const [customSlots, setCustomSlots] = useState([]);
  const [isRecreatingSchedule, setIsRecreatingSchedule] = useState(false);
  const [scheduleSuccessMsg, setScheduleSuccessMsg] = useState(false);
  const [scheduleSeed, setScheduleSeed] = useState(0);

  async function handleRecreateSchedule() {
    setIsRecreatingSchedule(true);
    setScheduleSuccessMsg(false);
    try {
      if (isApiOnline) {
        const res = await fetch(`${API_BASE}/plan/schedule`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            mode: sessionLengthMode,
            session_length_mode: sessionLengthMode,
            initial_session_duration: initialSessionDuration,
            session_duration: sessionDuration,
            free_time_windows: freeTimeWindows,
            custom_slots: []
          })
        });
        if (res.ok) {
          const data = await res.json();
          setTodayPlan(data);
        }
      }
    } catch (e) {
      console.warn('Recreate schedule fallback', e);
    } finally {
      setCustomSlots([]);
      setScheduleSeed(prev => prev + 1);
      setTimeout(() => {
        setIsRecreatingSchedule(false);
        setScheduleSuccessMsg(true);
        setTimeout(() => setScheduleSuccessMsg(false), 2500);
      }, 350);
    }
  }

  // ---------------------------------------------------------------------------
  // AI Study Features State & Handlers
  // ---------------------------------------------------------------------------
  const [subjectsList, setSubjectsList] = useState([
    'Operating Systems',
    'Artificial Intelligence',
    'Distributed Systems',
    'Mathematics'
  ]);
  const [showAddSubjectInput, setShowAddSubjectInput] = useState(false);
  const [newSubjectName, setNewSubjectName] = useState('');

  async function handleSaveSettings(overrideSettings) {
    const toSave = overrideSettings || settings;
    setSettingsSaving(true);
    try {
      if (isApiOnline) {
        const payload = {
          daily_minutes: Number(toSave.daily_minutes),
          retention_threshold: Number(toSave.retention_threshold),
          subject_priorities: toSave.subject_priorities,
          exam_dates: toSave.exam_dates
        };
        const res = await fetch(`${API_BASE}/settings`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (res.ok) {
          const updated = await res.json();
          setSettings(prev => ({ ...prev, ...updated }));
          setSettingsSavedToast(true);
          setTimeout(() => setSettingsSavedToast(false), 3000);
          loadDashboard();
          loadWeekPlan();
          loadTodayPlan();
        }
      } else {
        setSettingsSavedToast(true);
        setTimeout(() => setSettingsSavedToast(false), 2500);
      }
    } catch (e) {
      console.warn('Error saving settings', e);
    } finally {
      setSettingsSaving(false);
    }
  }

  async function handleTestGeminiKey() {
    setGeminiTesting(true);
    try {
      const res = await fetch(`${API_BASE}/ai/status`);
      if (res.ok) {
        const data = await res.json();
        setGeminiStatus({
          ...data,
          healthy: Boolean(data.healthy || data.status === 'connected')
        });
      }
    } catch (e) {
      console.warn('Test Gemini error', e);
      setGeminiStatus({ configured: false, healthy: false, message: 'Could not connect to backend server' });
    } finally {
      setGeminiTesting(false);
    }
  }

  async function handleAddNewSubject(customName, customColor, customPriority) {
    const name = (typeof customName === 'string' && customName.trim()) ? customName.trim() : newSubjectName.trim();
    if (!name) return;
    const color = customColor || newSubjectColor || '#32604e';
    const priority = parseFloat(customPriority || newSubjectPriority || 1.2);

    try {
      if (isApiOnline) {
        const res = await fetch(`${API_BASE}/subjects`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name,
            color,
            default_priority: priority
          })
        });
        if (res.ok) {
          await loadSubjects();
          await loadDashboard();
          await loadConcepts();
          await loadWeekPlan();
        }
      }
    } catch (e) {
      console.warn('Add subject backend fallback', e);
    }

    setSubjectsList(prev => {
      if (prev.some(s => s.toLowerCase() === name.toLowerCase())) return prev;
      return [...prev, name];
    });
    setSettings(prev => ({
      ...prev,
      subject_priorities: { ...prev.subject_priorities, [name]: priority },
      exam_dates: {
        ...prev.exam_dates,
        [name]: prev.exam_dates[name] || new Date(Date.now() + 14 * 86400000).toISOString().split('T')[0]
      }
    }));

    setChatSubject(name);
    setNewSubjectName('');
    setShowAddSubjectInput(false);
  }

  async function handleDeleteSubject(subjName) {
    if (!subjName) return;
    if (subjectsList.length <= 1) {
      alert("At least one subject must be tracked.");
      return;
    }
    if (!confirm(`Are you sure you want to remove "${subjName}" from your active study subjects?`)) {
      return;
    }

    try {
      if (isApiOnline) {
        await fetch(`${API_BASE}/subjects/${encodeURIComponent(subjName)}`, {
          method: 'DELETE'
        });
        await loadSubjects();
        await loadDashboard();
        await loadConcepts();
        await loadWeekPlan();
      }
    } catch (e) {
      console.warn('Delete subject backend fallback', e);
    }

    const remaining = subjectsList.filter(s => s.toLowerCase() !== subjName.toLowerCase());
    setSubjectsList(remaining);
    setSettings(prev => {
      const p = { ...prev.subject_priorities };
      const ex = { ...prev.exam_dates };
      delete p[subjName];
      delete ex[subjName];
      return { ...prev, subject_priorities: p, exam_dates: ex };
    });

    if (chatSubject.toLowerCase() === subjName.toLowerCase()) {
      setChatSubject(remaining[0] || 'Operating Systems');
    }
  }

  const [chatSubject, setChatSubject] = useState('Operating Systems');
  const [chatMessages, setChatMessages] = useState(() => [
    createDefaultConceptsMessage('Operating Systems', initClientConcepts(), [
      {
        id: "mat-os-1",
        subject: "Operating Systems",
        topic: "Virtual Memory & Concurrency",
        title: "Virtual Memory Paging and Deadlock Conditions",
        content: "Clock (Second-Chance) page replacement uses a circular list and a reference bit. When a page fault occurs, if the pointed page has use bit = 1, it resets it to 0 and advances; if 0, it selects it for eviction. The four necessary Coffman deadlock conditions are: 1) Mutual Exclusion, 2) Hold and Wait, 3) No Preemption, 4) Circular Wait."
      }
    ])
  ]);
  const [chatInput, setChatInput] = useState('');
  const [chatPersona, setChatPersona] = useState('socratic');
  const [chatLoading, setChatLoading] = useState(false);

  // Whenever subject changes, update default welcome message displaying the main concepts
  useEffect(() => {
    setChatMessages([createDefaultConceptsMessage(chatSubject, concepts, uploadedMaterials)]);
  }, [chatSubject]);

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

  // Sidebar File Processing (PDF / Word DOCX / PPT / text)
  async function handleSidebarProcessFile(file) {
    if (!file) return;
    const fileId = `sb-file-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`;
    const lowerName = file.name.toLowerCase();
    let fileType = 'text';
    if (lowerName.endsWith('.pdf')) fileType = 'pdf';
    else if (lowerName.endsWith('.docx') || lowerName.endsWith('.doc')) fileType = 'docx';
    else if (lowerName.endsWith('.pptx') || lowerName.endsWith('.ppt')) fileType = 'pptx';

    const cleanTitle = file.name.replace(/\.[^/.]+$/, "").replace(/[-_]/g, ' ');
    if (!sidebarUploadTitle.trim()) {
      setSidebarUploadTitle(cleanTitle);
    }

    const newStaged = {
      id: fileId,
      name: file.name,
      size: `${(file.size / 1024).toFixed(1)} KB`,
      status: 'extracting',
      text: '',
      pageCount: 1,
      fileType: fileType
    };
    setSidebarStagedFiles(prev => [...prev, newStaged]);
    setSidebarExtracting(true);

    try {
      if (['pdf', 'docx', 'pptx'].includes(fileType)) {
        const formData = new FormData();
        formData.append('file', file);
        const res = await fetch(`${API_BASE}/materials/extract-file`, {
          method: 'POST',
          body: formData
        });
        if (res.ok) {
          const data = await res.json();
          setSidebarStagedFiles(prev => prev.map(f => f.id === fileId ? {
            ...f,
            status: 'ready',
            text: data.text,
            pageCount: data.page_count || 1,
            fileType: data.file_type || fileType
          } : f));
          setSidebarExtracting(false);
          return;
        }
      } else {
        const text = await file.text();
        setSidebarStagedFiles(prev => prev.map(f => f.id === fileId ? {
          ...f,
          status: 'ready',
          text: text,
          pageCount: 1,
          fileType: 'text'
        } : f));
        setSidebarExtracting(false);
        return;
      }
    } catch (err) {
      console.warn('Sidebar file extraction fallback', err);
    }

    // Fallback extraction
    try {
      const text = await file.text();
      setSidebarStagedFiles(prev => prev.map(f => f.id === fileId ? {
        ...f,
        status: 'ready',
        text: text.slice(0, 5000),
        pageCount: 1,
        fileType: fileType
      } : f));
    } catch {
      setSidebarStagedFiles(prev => prev.map(f => f.id === fileId ? {
        ...f,
        status: 'ready',
        text: `Content extracted from ${file.name}.`,
        pageCount: 1,
        fileType: fileType
      } : f));
    }
    setSidebarExtracting(false);
  }

  async function handleSidebarUploadSubmit(e) {
    if (e && e.preventDefault) e.preventDefault();
    const targetSubject = chatSubject === 'All' ? 'General' : chatSubject;
    const contentFromFiles = sidebarStagedFiles.map(f => f.text).filter(Boolean).join('\n\n');
    const contentToIngest = (sidebarUploadContent.trim() + '\n\n' + contentFromFiles).trim();

    // Derive a clean, fitting title directly from the uploaded file or source content
    let titleToUse = '';
    if (sidebarStagedFiles[0]?.name) {
      titleToUse = sidebarStagedFiles[0].name.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ').trim();
    } else if (sidebarUploadContent.trim()) {
      const firstLine = sidebarUploadContent.trim().split('\n')[0].replace(/^[#*\-•\s]+/, '').trim();
      if (firstLine && firstLine.length > 2) {
        titleToUse = firstLine.length > 40 ? firstLine.slice(0, 37) + '...' : firstLine;
      }
    }
    if (!titleToUse) {
      titleToUse = `${targetSubject} Notes (${new Date().toLocaleDateString([], { month: 'short', day: 'numeric' })})`;
    }
    const topicToUse = targetSubject;

    setSidebarUploading(true);
    setSidebarUploadSuccess(false);

    try {
      if (isApiOnline) {
        const res = await fetch(`${API_BASE}/materials`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            subject: targetSubject,
            topic: topicToUse,
            title: titleToUse,
            content: contentToIngest
          })
        });
        if (res.ok) {
          const data = await res.json();
          if (data.concept) {
            setConcepts(prev => [data.concept, ...prev]);
          }
          if (data.generated_questions) {
            setQuestions(prev => [...data.generated_questions, ...prev]);
          }
          const newMat = {
            id: `mat-${Date.now()}`,
            subject: targetSubject,
            topic: topicToUse,
            title: titleToUse,
            content: contentToIngest
          };
          setUploadedMaterials(prev => [newMat, ...prev]);
          setSidebarStagedFiles([]);
          setSidebarUploadTitle('');
          setSidebarUploadContent('');
          setSidebarUploading(false);
          setSidebarUploadSuccess(true);
          setTimeout(() => setSidebarUploadSuccess(false), 3000);
          return;
        }
      }
    } catch (err) {
      console.warn('Backend material upload failed', err);
    }

    // Client fallback
    const newId = `c-usr-${Date.now()}`;
    const newConcept = {
      id: newId,
      subject: targetSubject,
      topic: topicToUse,
      name: titleToUse,
      difficulty: 'Medium',
      n_right: 0,
      n_wrong: 0,
      days_ago: 0,
      last_practiced_at: new Date().toISOString(),
      half_life_days: 1.0,
      p_hat: 0.99,
      is_due: false,
      delta_days: 0.0
    };
    setConcepts(prev => [newConcept, ...prev]);
    setUploadedMaterials(prev => [{
      id: `mat-${Date.now()}`,
      subject: targetSubject,
      topic: topicToUse,
      title: titleToUse,
      content: contentToIngest
    }, ...prev]);
    setSidebarStagedFiles([]);
    setSidebarUploadTitle('');
    setSidebarUploadContent('');
    setSidebarUploading(false);
    setSidebarUploadSuccess(true);
    setTimeout(() => setSidebarUploadSuccess(false), 3000);
  }

  function handleDeleteMaterial(matId) {
    setUploadedMaterials(prev => prev.filter(m => m.id !== matId));
  }

  // File processing (PDF / Word DOCX / PPT / text / paste)
  async function handleProcessFile(file) {
    if (!file) return;
    const fileId = `file-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`;
    const lowerName = file.name.toLowerCase();
    const isDoc = lowerName.match(/\.(pdf|docx|doc|pptx|ppt)$/);

    const newStaged = {
      id: fileId,
      name: file.name,
      size: `${(file.size / 1024).toFixed(1)} KB`,
      status: 'extracting',
      text: '',
      pageCount: 1
    };
    setStagedFiles(prev => [...prev, newStaged]);
    setExtractingFile(true);

    try {
      if (isDoc) {
        const formData = new FormData();
        formData.append('file', file);
        const res = await fetch(`${API_BASE}/materials/extract-file`, {
          method: 'POST',
          body: formData
        });
        if (res.ok) {
          const data = await res.json();
          setStagedFiles(prev => prev.map(f => f.id === fileId ? {
            ...f,
            status: 'ready',
            text: data.text,
            pageCount: data.page_count || 1
          } : f));
          setExtractingFile(false);
          return;
        }
      } else {
        const text = await file.text();
        setStagedFiles(prev => prev.map(f => f.id === fileId ? {
          ...f,
          status: 'ready',
          text: text,
          pageCount: 1
        } : f));
        setExtractingFile(false);
        return;
      }
    } catch (err) {
      console.warn('File extraction error', err);
    }

    // Client fallback
    try {
      const text = await file.text();
      setStagedFiles(prev => prev.map(f => f.id === fileId ? {
        ...f,
        status: 'ready',
        text: text.slice(0, 5000),
        pageCount: 1
      } : f));
    } catch {
      setStagedFiles(prev => prev.map(f => f.id === fileId ? {
        ...f,
        status: 'ready',
        text: `Content extracted from ${file.name}.`,
        pageCount: 1
      } : f));
    }
    setExtractingFile(false);
  }

  function handlePaste(e) {
    if (e.clipboardData && e.clipboardData.files && e.clipboardData.files.length > 0) {
      e.preventDefault();
      handleProcessFile(e.clipboardData.files[0]);
    }
  }

  function handleDragOver(e) {
    e.preventDefault();
    setIsDragging(true);
  }

  function handleDragLeave(e) {
    e.preventDefault();
    setIsDragging(false);
  }

  function handleDrop(e) {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleProcessFile(e.dataTransfer.files[0]);
    }
  }

  async function handleSendChatMessage(textToSend = null) {
    const text = (textToSend || chatInput).trim();
    if ((!text && stagedFiles.length === 0) || chatLoading) return;

    const currentFiles = [...stagedFiles];
    let fileBadge = "";
    if (currentFiles.length > 0) {
      fileBadge = ` [Attached: ${currentFiles.map(f => f.name).join(', ')}]`;
    }

    const displayText = text || `I have attached ${currentFiles.map(f => f.name).join(', ')}. Please clear my doubts on this material.`;

    const userMsg = {
      role: 'user',
      content: displayText + (text && fileBadge ? `\n\n*(📎 ${currentFiles.map(f => f.name).join(', ')})*` : ''),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setChatMessages(prev => [...prev, userMsg]);
    setChatInput('');
    setChatLoading(true);

    const stagedContext = currentFiles.map(f => `[Uploaded Document: ${f.name}]\n${f.text}`).join('\n\n');

    try {
      if (isApiOnline) {
        const res = await fetch(`${API_BASE}/ai/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: displayText,
            history: chatMessages.slice(-6).map(m => ({ role: m.role, content: m.content })),
            subject: chatSubject === 'All' ? null : chatSubject,
            persona: chatPersona,
            materials_context: stagedContext || null
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
              aiPowered: data.ai_powered,
              model: data.model,
              cited_materials: data.cited_materials || [chatSubject]
            }
          ]);
          setChatLoading(false);
          if (currentFiles.length > 0) {
            currentFiles.forEach(f => {
              if (f.text && !uploadedMaterials.some(m => m.title === f.name)) {
                setUploadedMaterials(prev => [{
                  id: `mat-${Date.now()}`,
                  subject: chatSubject === 'All' ? 'General' : chatSubject,
                  topic: chatSubject,
                  title: f.name,
                  content: f.text
                }, ...prev]);
              }
            });
            setStagedFiles([]);
          }
          return;
        }
      }
    } catch (e) {
      console.warn('Chat request fallback', e);
    }

    // Client-side local fallback
    setTimeout(() => {
      const subjectMaterials = uploadedMaterials.filter(m => chatSubject === 'All' || m.subject.toLowerCase() === chatSubject.toLowerCase());
      const rawNotes = currentFiles[0]?.text || subjectMaterials[0]?.content || "";
      const excerpt = rawNotes.slice(0, 240);

      const fallbackReplies = {
        socratic: `Regarding your doubt in **${chatSubject === 'All' ? 'your uploaded studies' : chatSubject}**, let's refer directly to your notes:\n\n> *\"${excerpt || 'Primary state machine invariant ensures fault tolerance and reliable transitions.'}...\"*\n\n**Core Intuition:** In **${chatSubject}**, the critical principle is maintaining bounded state transitions. When you asked *\"${displayText.slice(0, 60)}\"*, consider: What invariant prevents this from corrupting system memory?`,
        exam_prep: `### High-Yield Doubt Resolution (${chatSubject})\n- **From Your Notes:** *\"${excerpt.slice(0, 160) || 'State invariant definition'}...\"*\n- **Key Exam Rule:** Under testing conditions, always identify the failure boundary and Coffman conditions first.\n- **Duolingo HLR Principle:** Each correct review doubles estimated half-life ($h = 2^{\\theta x}$), preventing exponential decay ($p = 2^{-\\Delta/h}$).`,
        eli5: `Think of your uploaded materials for **${chatSubject}** like a safety instruction card on an airplane! It says: *\"${excerpt.slice(0, 130) || 'Keep all channels clear and verified'}...\"*\n\nIn plain English: you always need a simple confirmation before making irreversible changes so nothing gets scrambled!`
      };

      setChatMessages(prev => [
        ...prev,
        {
          role: 'model',
          content: fallbackReplies[chatPersona] || fallbackReplies.socratic,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          followups: [
            `Can you quiz me on ${chatSubject}?`,
            `What is a real-world software example from these notes?`,
            `How does this connect to my exam plan?`
          ],
          aiPowered: false,
          cited_materials: [chatSubject]
        }
      ]);
      setChatLoading(false);
      setStagedFiles([]);
    }, 600);
  }

  async function handleIngestStagedMaterial() {
    const file = stagedFiles[0];
    const contentToIngest = (file?.text || chatInput).trim();
    if (!contentToIngest) return;

    const titleToUse = file?.name?.replace(/\.[^/.]+$/, '') || materialForm.title || `${chatSubject} Study Excerpt`;
    const topicToUse = materialForm.topic || chatSubject;
    const targetSubject = chatSubject === 'All' ? 'Operating Systems' : chatSubject;

    setUploading(true);
    setUploadSuccess(false);

    try {
      if (isApiOnline) {
        const res = await fetch(`${API_BASE}/materials`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            subject: targetSubject,
            topic: topicToUse,
            title: titleToUse,
            content: contentToIngest
          })
        });
        if (res.ok) {
          const data = await res.json();
          if (data.concept) {
            setConcepts(prev => [data.concept, ...prev]);
            setSelectedConceptId(data.concept.id);
          }
          if (data.generated_questions) {
            setQuestions(prev => [...data.generated_questions, ...prev]);
          }
          const newMat = {
            id: `mat-${Date.now()}`,
            subject: targetSubject,
            topic: topicToUse,
            title: titleToUse,
            content: contentToIngest
          };
          setUploadedMaterials(prev => [newMat, ...prev]);
          setStagedFiles([]);
          setChatInput('');
          setUploading(false);
          setUploadSuccess(true);
          setChatMessages(prev => [
            ...prev,
            {
              role: 'model',
              content: `✓ **${titleToUse}** has been ingested into your **${targetSubject}** knowledge base!\n\nExtracted concepts and synthesized questions have been added to your Active Recall pool. The Chatbot is now grounded in this material—ask any doubt or launch the quiz on the right!`,
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              followups: [
                `Test my knowledge on ${titleToUse}`,
                `Summarize key concepts from ${titleToUse}`,
                `What are the most difficult exam questions on this?`
              ],
              aiPowered: true
            }
          ]);
          return;
        }
      }
    } catch (err) {
      console.warn('Material upload fallback', err);
    }

    // Client fallback
    const newId = `c-usr-${Date.now()}`;
    const newConcept = {
      id: newId,
      subject: targetSubject,
      topic: topicToUse,
      name: titleToUse,
      difficulty: 'Medium',
      n_right: 0,
      n_wrong: 0,
      days_ago: 0,
      last_practiced_at: new Date().toISOString(),
      half_life_days: 1.0,
      p_hat: 0.99,
      is_due: false,
      delta_days: 0.0
    };
    setConcepts(prev => [newConcept, ...prev]);
    setUploadedMaterials(prev => [{
      id: `mat-${Date.now()}`,
      subject: targetSubject,
      topic: topicToUse,
      title: titleToUse,
      content: contentToIngest
    }, ...prev]);
    setStagedFiles([]);
    setChatInput('');
    setUploading(false);
    setUploadSuccess(true);
    setChatMessages(prev => [
      ...prev,
      {
        role: 'model',
        content: `✓ Added **${titleToUse}** to your **${targetSubject}** materials. Ask me any doubt about it!`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        followups: [
          `Explain the core mechanism in simple terms`,
          `Quiz me on ${titleToUse}`
        ],
        aiPowered: false
      }
    ]);
  }
  async function handleSolveDoubt(presetDoubt = null) {
    const text = presetDoubt || doubtInput;
    if (!text.trim()) return;

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
        loadMaterials();
        loadSubjects();
        loadSettings();
        loadWeekPlan();
        loadGeminiStatus();
      } else {
        setIsApiOnline(false);
      }
    } catch {
      setIsApiOnline(false);
    }
  }

  async function loadSubjects() {
    try {
      const res = await fetch(`${API_BASE}/subjects`);
      if (res.ok) {
        const data = await res.json();
        if (data && data.length > 0) {
          setSubjectsDetails(data);
          const names = data.map(s => s.name);
          setSubjectsList(names);
          setSettings(prev => {
            const updatedPrio = { ...prev.subject_priorities };
            const updatedExams = { ...prev.exam_dates };
            data.forEach(s => {
              if (updatedPrio[s.name] === undefined) {
                updatedPrio[s.name] = s.default_priority || 1.0;
              }
              if (!updatedExams[s.name]) {
                const d = new Date();
                d.setDate(d.getDate() + 14);
                updatedExams[s.name] = d.toISOString().split('T')[0];
              }
            });
            return { ...prev, subject_priorities: updatedPrio, exam_dates: updatedExams };
          });
        }
      }
    } catch (e) {
      console.warn('loadSubjects fallback', e);
    }
  }

  async function loadSettings() {
    try {
      const res = await fetch(`${API_BASE}/settings`);
      if (res.ok) {
        const data = await res.json();
        setSettings(prev => ({
          ...prev,
          daily_minutes: data.daily_minutes || prev.daily_minutes,
          retention_threshold: data.retention_threshold !== undefined ? data.retention_threshold : prev.retention_threshold,
          subject_priorities: data.subject_priorities || prev.subject_priorities,
          exam_dates: data.exam_dates || prev.exam_dates
        }));
        if (data.gemini_configured !== undefined) {
          setGeminiStatus(prev => ({
            ...prev,
            configured: data.gemini_configured,
            healthy: data.gemini_configured
          }));
        }
      }
    } catch (e) {
      console.warn('loadSettings fallback', e);
    }
  }

  async function loadWeekPlan() {
    try {
      const res = await fetch(`${API_BASE}/plan/week`);
      if (res.ok) {
        const data = await res.json();
        setWeekPlan(data);
      }
    } catch (e) {
      console.warn('loadWeekPlan fallback', e);
    }
  }

  async function loadGeminiStatus() {
    try {
      const res = await fetch(`${API_BASE}/ai/status`);
      if (res.ok) {
        const data = await res.json();
        setGeminiStatus({
          ...data,
          healthy: Boolean(data.healthy || data.status === 'connected')
        });
      }
    } catch (e) {
      console.warn('loadGeminiStatus fallback', e);
    }
  }

  async function loadMaterials() {
    try {
      const res = await fetch(`${API_BASE}/materials`);
      if (res.ok) {
        const data = await res.json();
        if (data && data.length > 0) {
          setUploadedMaterials(data);
        }
      }
    } catch (e) {
      console.warn('Could not load materials from backend', e);
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

  // ---------------------------------------------------------------------------
  // Time Parsing & Slicing Helpers for Study Planner
  // ---------------------------------------------------------------------------
  function parseTimeToMinutes(tStr) {
    if (!tStr) return 450;
    const str = String(tStr).trim();
    if (str.toUpperCase().includes('AM') || str.toUpperCase().includes('PM')) {
      const match = str.match(/(\d+):(\d+)\s*(AM|PM)/i);
      if (match) {
        let h = parseInt(match[1], 10);
        const m = parseInt(match[2], 10);
        const period = match[3].toUpperCase();
        if (period === 'PM' && h < 12) h += 12;
        if (period === 'AM' && h === 12) h = 0;
        return h * 60 + m;
      }
    }
    const parts = str.split(':');
    return parseInt(parts[0], 10) * 60 + parseInt(parts[1] || '0', 10);
  }

  function formatMinutesToTime(totalMins) {
    const mins = ((totalMins % 1440) + 1440) % 1440;
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    const period = h < 12 ? 'AM' : 'PM';
    const h12 = h % 12 === 0 ? 12 : h % 12;
    return `${String(h12).padStart(2, '0')}:${String(m).padStart(2, '0')} ${period}`;
  }

  function formatStripTimeSlot(startStr, endStr) {
    if (!startStr || !endStr) return '';
    const clean = s => s.trim().replace(/^0/, '').toLowerCase();
    return `${clean(startStr)} to ${clean(endStr)}`;
  }

  function getCognitiveTier(startMins) {
    const m = ((startMins % 1440) + 1440) % 1440;
    if (m >= 360 && m < 690) return '🧠 Cognitive Peak';
    if (m >= 690 && m < 840) return '🌱 Steady Flow';
    if (m >= 840 && m < 1050) return '⚡ High Energy';
    if (m >= 1050 && m < 1230) return '🌅 Active Consolidation';
    return '🌙 Night Review';
  }

  function handleAddFreeTimeWindow() {
    if (!newWindowStart || !newWindowEnd) return;
    const newWin = {
      id: `win-${Date.now()}`,
      start: newWindowStart,
      end: newWindowEnd,
      label: newWindowLabel.trim() || 'Study Window'
    };
    setFreeTimeWindows(prev => [...prev, newWin]);
    setShowAddWindow(false);
  }

  function handleRemoveFreeTimeWindow(winId) {
    setFreeTimeWindows(prev => prev.filter(w => w.id !== winId));
  }

  function handleMoveWindowUp(index) {
    if (index <= 0) return;
    setFreeTimeWindows(prev => {
      const next = [...prev];
      const temp = next[index - 1];
      next[index - 1] = next[index];
      next[index] = temp;
      return next;
    });
  }

  function handleMoveWindowDown(index) {
    if (index >= freeTimeWindows.length - 1) return;
    setFreeTimeWindows(prev => {
      const next = [...prev];
      const temp = next[index + 1];
      next[index + 1] = next[index];
      next[index] = temp;
      return next;
    });
  }

  function handleApplyWindowPreset(presetType) {
    if (presetType === 'morning_evening') {
      setFreeTimeWindows([
        { id: 'win-1', start: '07:00', end: '08:30', label: 'Morning High Focus' },
        { id: 'win-2', start: '20:00', end: '21:30', label: 'Evening Review' }
      ]);
    } else if (presetType === 'afternoon') {
      setFreeTimeWindows([
        { id: 'win-aft', start: '14:00', end: '16:00', label: 'Afternoon Deep Work' }
      ]);
    } else if (presetType === 'full_academic') {
      setFreeTimeWindows([
        { id: 'win-ac1', start: '08:00', end: '10:00', label: 'Morning Deep Work' },
        { id: 'win-ac2', start: '15:00', end: '17:00', label: 'Afternoon Focus' },
        { id: 'win-ac3', start: '20:30', end: '22:00', label: 'Evening Session' }
      ]);
    }
  }

  function handleToggleTileCompleted(tileId) {
    setCompletedTileIds(prev => {
      const next = new Set(prev);
      if (next.has(tileId)) {
        next.delete(tileId);
      } else {
        next.add(tileId);
      }
      return next;
    });
  }

  function handleUpdateManualTile(tileId, field, value) {
    setCustomSlots(prev => {
      const existing = prev.find(s => s.id === tileId);
      if (existing) {
        return prev.map(s => s.id === tileId ? { ...s, [field]: value } : s);
      } else {
        return [...prev, { id: tileId, [field]: value }];
      }
    });
  }

  const planSchedule = useMemo(() => {
    const subjects = [...new Set(concepts.map(c => c.subject))];

    // Quiz data analysis for AI optimal session length:
    const totalRight = concepts.reduce((acc, c) => acc + (c.n_right || 0), 0);
    const totalWrong = concepts.reduce((acc, c) => acc + (c.n_wrong || 0), 0);
    const totalQAttempts = totalRight + totalWrong;
    const avgAccuracy = totalQAttempts > 0 ? (totalRight / totalQAttempts) : 0.70;
    const highDecayCount = concepts.filter(c => (c.p_hat || 0.70) < 0.65 || c.is_due).length;

    let effectiveDuration = sessionDuration;
    let aiOptimization = null;

    if (sessionLengthMode === 'ai_optimized') {
      const baseD = [20, 30, 45].includes(Number(initialSessionDuration)) ? Number(initialSessionDuration) : 30;
      let optimalD = 30;
      let reason = '';
      if (avgAccuracy < 0.65 || highDecayCount >= 3) {
        optimalD = 20;
        reason = `AI tuned session length to 20m (from initial ${baseD}m): Quiz data indicates ${highDecayCount} concepts with memory decay. Shorter intervals optimize retention and prevent cognitive fatigue.`;
      } else if (avgAccuracy > 0.85 && highDecayCount <= 1) {
        optimalD = baseD >= 30 ? 45 : 30;
        reason = `AI fixed session length to ${optimalD}m (from initial ${baseD}m): High quiz score (${Math.round(avgAccuracy * 100)}% accuracy) supports extended deep work sessions.`;
      } else {
        optimalD = 30;
        reason = `AI fixed session length to 30m: Balanced focus duration for active recall and steady memory consolidation.`;
      }
      effectiveDuration = optimalD;
      aiOptimization = {
        mode: 'ai_optimized',
        initial_duration: baseD,
        optimal_duration: optimalD,
        avg_accuracy: avgAccuracy,
        high_decay_count: highDecayCount,
        reason
      };
    } else {
      effectiveDuration = [20, 30, 45].includes(Number(sessionDuration)) ? Number(sessionDuration) : 30;
      aiOptimization = {
        mode: 'manual',
        initial_duration: effectiveDuration,
        optimal_duration: effectiveDuration,
        avg_accuracy: avgAccuracy,
        high_decay_count: highDecayCount,
        reason: `Manual mode: Session duration locked at ${effectiveDuration}m by your selection.`
      };
    }

    const duration = effectiveDuration;

    // 1. Availability Slicing: Slice free-time windows into uniform duration blocks
    // Eliminates erratic micro-durations (< sessionDuration)
    const slicedSlots = [];
    (freeTimeWindows || []).forEach(w => {
      try {
        const startM = parseTimeToMinutes(w.start);
        let endM = parseTimeToMinutes(w.end);
        if (endM <= startM) endM += 1440;
        const totalWindow = endM - startM;
        const numBlocks = Math.floor(totalWindow / duration);
        let curS = startM;
        for (let i = 0; i < numBlocks; i++) {
          const curE = curS + duration;
          const sFmt = formatMinutesToTime(curS);
          const eFmt = formatMinutesToTime(curE);
          slicedSlots.push({
            start_mins: curS % 1440,
            end_mins: curE % 1440,
            start_time: sFmt,
            end_time: eFmt,
            time_slot: `${sFmt} - ${eFmt}`,
            time_slot_formatted: formatStripTimeSlot(sFmt, eFmt),
            duration_minutes: duration,
            cognitive_tier: getCognitiveTier(curS % 1440),
            window_label: w.label || 'Availability Window'
          });
          curS = curE;
        }
      } catch (e) {
        console.warn('Window slice error', e);
      }
    });

    // Fallback if no valid windows
    if (slicedSlots.length === 0) {
      const anchorM = 450; // 07:30 AM
      let curS = anchorM;
      for (let i = 0; i < 3; i++) {
        const curE = curS + duration;
        const sFmt = formatMinutesToTime(curS);
        const eFmt = formatMinutesToTime(curE);
        slicedSlots.push({
          start_mins: curS % 1440,
          end_mins: curE % 1440,
          start_time: sFmt,
          end_time: eFmt,
          time_slot: `${sFmt} - ${eFmt}`,
          time_slot_formatted: formatStripTimeSlot(sFmt, eFmt),
          duration_minutes: duration,
          cognitive_tier: getCognitiveTier(curS % 1440),
          window_label: 'AI-Optimized Slot'
        });
        curS = curE + 10;
      }
    }

    // 2. Evaluate Weak & Difficult Concepts from HLR, Nominal Difficulty, and Quiz Analytics
    const diffWeights = { 'Hard': 3.5, 'Medium': 2.0, 'Easy': 1.0 };
    const evaluatedConcepts = concepts.map(c => {
      const nw = c.n_wrong || 0;
      const nr = c.n_right || 0;
      const dWeight = diffWeights[c.difficulty] || 2.0;
      const weakness = (1.0 - (c.p_hat || 0.8)) * 2.0 + (nw / Math.max(1, nw + nr)) * 1.5 + (c.is_due ? 1.0 : 0.0);
      const difficultyScore = (dWeight * 2.0) + (weakness * 1.5) + (c.is_due ? 1.0 : 0.0);
      return {
        ...c,
        difficulty_score: difficultyScore,
        weakness_score: weakness
      };
    });

    // Rank subjects by difficulty: most difficult subjects first
    const subjectDifficulties = {};
    subjects.forEach(subj => {
      const sc = evaluatedConcepts.filter(c => c.subject === subj);
      const avgDiff = sc.reduce((acc, c) => acc + c.difficulty_score, 0) / Math.max(1, sc.length);
      const hardCount = sc.filter(c => c.difficulty === 'Hard').length;
      const prio = settings.subject_priorities[subj] || 1.0;
      // Combined subject difficulty: concept hardness, errors, and priority
      subjectDifficulties[subj] = (avgDiff * 2.0) + (hardCount * 1.5) + prio;
    });

    // Ranked subjects: most difficult subject at index 0, so slots on top of the list receive the hardest subjects
    const rankedSubjects = [...subjects].sort((a, b) => (subjectDifficulties[b] || 1) - (subjectDifficulties[a] || 1));
    const rankedConcepts = [...evaluatedConcepts].sort((a, b) => b.difficulty_score - a.difficulty_score);

    // 3. Build Interactive Strips / Tiles
    const tiles = [];
    const usedConceptIds = new Set();

    slicedSlots.forEach((slot, idx) => {
      const tileId = `tile-${idx + 1}`;
      const manualOverride = customSlots.find(s => s.id === tileId);

      // Determine subject: slots on the top of the list get the most difficult subjects
      const assignedSubject = manualOverride?.subject || rankedSubjects[idx % Math.max(1, rankedSubjects.length)] || 'Operating Systems';

      // Determine specific weak concept:
      let chosenConcept = null;
      if (manualOverride?.target_concept_id) {
        chosenConcept = concepts.find(c => c.id === manualOverride.target_concept_id);
      }
      if (!chosenConcept) {
        const subjWeak = rankedConcepts.filter(c => c.subject === assignedSubject && !usedConceptIds.has(c.id));
        chosenConcept = subjWeak[0] || rankedConcepts.find(c => c.subject === assignedSubject) || rankedConcepts[0];
      }

      if (chosenConcept) {
        usedConceptIds.add(chosenConcept.id);
      }

      const pPct = Math.round((chosenConcept?.p_hat || 0.8) * 100);
      const urgencyTxt = (chosenConcept?.p_hat || 0.8) < 0.50
        ? `Critical memory decay (${pPct}% recall, h=${chosenConcept?.half_life_days || 1}d)`
        : chosenConcept?.is_due
        ? `Due for active recall review (${pPct}% retention threshold)`
        : `Sustained memory consolidation (${pPct}% recall)`;

      tiles.push({
        id: tileId,
        time_slot: slot.time_slot,
        time_slot_formatted: slot.time_slot_formatted || formatStripTimeSlot(slot.start_time, slot.end_time),
        start_time: slot.start_time,
        end_time: slot.end_time,
        duration_minutes: slot.duration_minutes,
        subject: assignedSubject,
        target_topic: chosenConcept?.name || 'Core Fundamentals',
        recommended_topic: `Recommended Topic: ${chosenConcept?.name || 'Core Fundamentals'}`,
        target_concept_id: chosenConcept?.id,
        target_concept: chosenConcept,
        concept_difficulty: chosenConcept?.difficulty || 'Medium',
        productivity_tier: slot.cognitive_tier,
        mode_tier: sessionLengthMode === 'ai_optimized' ? 'AI-Optimized' : 'Manual',
        urgency_reason: urgencyTxt,
        decay_p: chosenConcept?.p_hat || 0.8,
        estimated_questions: Math.max(3, Math.min(8, Math.round(duration / 5))),
        is_completed: completedTileIds.has(tileId),
        status: completedTileIds.has(tileId) ? 'completed' : 'ready'
      });
    });

    // 4. Construct Blocks for backward compatibility
    const blocks = rankedSubjects.map(subj => {
      const subjTiles = tiles.filter(t => t.subject === subj);
      const subjConcepts = subjTiles.map(t => t.target_concept).filter(Boolean);
      return {
        id: `block-${subj.toLowerCase().replace(/\s+/g, '-')}`,
        subject: subj,
        allocated_minutes: subjTiles.reduce((a, b) => a + b.duration_minutes, 0),
        estimated_questions: subjTiles.reduce((a, b) => a + b.estimated_questions, 0),
        avg_p_hat: subjTiles.length ? parseFloat((subjTiles.reduce((a, b) => a + b.decay_p, 0) / subjTiles.length).toFixed(3)) : 0.8,
        concepts: subjConcepts.length ? subjConcepts : concepts.filter(c => c.subject === subj).slice(0, 2)
      };
    }).filter(b => b.allocated_minutes > 0);

    return {
      date: new Date().toISOString().split('T')[0],
      mode: sessionLengthMode,
      session_length_mode: sessionLengthMode,
      session_duration: duration,
      initial_session_duration: initialSessionDuration,
      optimal_session_duration: duration,
      ai_duration_optimization: aiOptimization,
      anchor_time: '07:30 AM',
      free_time_windows: freeTimeWindows,
      daily_minutes_goal: settings.daily_minutes,
      total_scheduled_minutes: tiles.reduce((a, b) => a + b.duration_minutes, 0),
      due_concepts_total: concepts.filter(c => c.is_due).length,
      tiles,
      strips: tiles,
      blocks: blocks.length ? blocks : [{ id: 'b-default', subject: 'Operating Systems', allocated_minutes: 30, estimated_questions: 5, avg_p_hat: 0.75, concepts: [] }]
    };
  }, [concepts, settings, sessionLengthMode, initialSessionDuration, sessionDuration, freeTimeWindows, customSlots, completedTileIds, scheduleSeed]);

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

  const subjectConcepts = useMemo(() => {
    return concepts.filter(c => chatSubject === 'All' || c.subject.toLowerCase() === chatSubject.toLowerCase());
  }, [concepts, chatSubject]);

  const subjectRecall = useMemo(() => {
    if (!subjectConcepts.length) return 85;
    const avg = subjectConcepts.reduce((acc, c) => acc + c.p_hat, 0) / subjectConcepts.length;
    return Math.round(avg * 100);
  }, [subjectConcepts]);

  const subjectDueCount = useMemo(() => {
    return subjectConcepts.filter(c => c.is_due).length;
  }, [subjectConcepts]);

  const subjectQuestionCount = useMemo(() => {
    return questions.filter(q => chatSubject === 'All' || q.subject.toLowerCase() === chatSubject.toLowerCase()).length;
  }, [questions, chatSubject]);

  const subjectMaterials = useMemo(() => {
    return uploadedMaterials.filter(m => chatSubject === 'All' || m.subject.toLowerCase() === chatSubject.toLowerCase());
  }, [uploadedMaterials, chatSubject]);

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
              className={`nav-tab-btn ${activeTab === 'materials' ? 'active' : ''}`}
              onClick={() => setActiveTab('materials')}
            >
              <BookOpen size={14} /> Materials & AI
            </button>
            <button
              className={`nav-tab-btn ${activeTab === 'mnemonics' ? 'active' : ''}`}
              onClick={() => setActiveTab('mnemonics')}
            >
              <Sparkles size={14} /> Mnemonic Lab
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
      <main className={`main-wrapper ${activeTab === 'materials' ? 'materials-active' : ''}`}>
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
                              setChatSubject(c.subject);
                              setChatInput(`I have a doubt about ${c.name} in ${c.subject}: What is the core mechanism and what common mistakes should I avoid?`);
                              setActiveTab('materials');
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

        {/* ================= SCREEN 2: TODAY'S PLAN (TILE-BASED ADAPTIVE SCHEDULER) ================= */}
        {activeTab === 'plan' && (
          <div className="animate-fade-in">
            {/* Plan Header */}
            <div className="section-header">
              <div>
                <h1 className="section-title">
                  <Calendar size={18} /> Adaptive HLR Study Planner
                </h1>
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <div className="badge badge-easy" style={{ padding: '6px 12px', fontSize: 11 }}>
                  <Layers size={12} /> {planSchedule.tiles?.length || 0} Uniform Sessions
                </div>
                <button
                  type="button"
                  className="btn-primary"
                  style={{
                    padding: '6px 14px',
                    fontSize: 12,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    background: scheduleSuccessMsg ? 'var(--mint-dark)' : undefined
                  }}
                  onClick={handleRecreateSchedule}
                  disabled={isRecreatingSchedule}
                  title="Re-create and re-slice your study schedule anytime after making changes"
                >
                  <RefreshCw size={13} className={isRecreatingSchedule ? 'animate-spin' : ''} />
                  {isRecreatingSchedule ? 'Re-creating...' : scheduleSuccessMsg ? '✓ Schedule Re-created!' : 'Re-create Schedule'}
                </button>
              </div>
            </div>

            {/* Controls Panel: Modes, Session Durations, Anchors & Availability Windows */}
            <div className="schedule-controls-panel">
              <div className="schedule-header-row">
                {/* 1. Session Length Mode Switcher (Manual vs AI-Optimized) */}
                <div>
                  <label style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', display: 'block', marginBottom: 6 }}>
                    Session Length Mode
                  </label>
                  <div className="mode-switcher-group">
                    <button
                      type="button"
                      className={`mode-pill-btn ${sessionLengthMode === 'manual' ? 'active' : ''}`}
                      onClick={() => setSessionLengthMode('manual')}
                      title="You manually select and lock your exact session duration"
                    >
                      <Sliders size={14} /> Manual Mode
                    </button>
                    <button
                      type="button"
                      className={`mode-pill-btn ${sessionLengthMode === 'ai_optimized' ? 'active' : ''}`}
                      onClick={() => setSessionLengthMode('ai_optimized')}
                      title="AI fixes towards optimal session length using your historical quiz performance and fatigue metrics"
                    >
                      <Sparkles size={14} color="var(--mint-dark)" /> AI-Optimized Mode
                    </button>
                  </div>
                </div>

                {/* 2. Session Length Selection based on Mode */}
                {sessionLengthMode === 'manual' ? (
                  <div>
                    <label style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', display: 'block', marginBottom: 6 }}>
                      Select Session Length (Fixed)
                    </label>
                    <div className="duration-pill-group">
                      {[20, 30, 45].map(mins => (
                        <button
                          key={mins}
                          type="button"
                          className={`duration-btn ${sessionDuration === mins ? 'active' : ''}`}
                          onClick={() => setSessionDuration(mins)}
                          title={`Lock in ${mins}-minute session length`}
                        >
                          {mins}m
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div>
                    <label style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', display: 'block', marginBottom: 6 }}>
                      Initial Baseline Length
                    </label>
                    <div className="duration-pill-group">
                      {[20, 30, 45].map(mins => (
                        <button
                          key={mins}
                          type="button"
                          className={`duration-btn ${initialSessionDuration === mins ? 'active' : ''}`}
                          onClick={() => setInitialSessionDuration(mins)}
                          title={`Initial baseline duration of ${mins}m for AI optimization`}
                        >
                          {mins}m baseline
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Free-Time Availability Windows Section */}
              <div className="free-windows-section">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
                  <div>
                    <span style={{ fontSize: 13, fontWeight: 800, color: 'var(--ink)' }}>
                      Availability Windows (Ranked by Willingness to Learn Difficult Subjects)
                    </span>
                  </div>

                  {/* Window Presets */}
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      className="btn-secondary btn-sm"
                      onClick={() => handleApplyWindowPreset('morning_evening')}
                      style={{ fontSize: 11, padding: '4px 8px' }}
                    >
                      🌅 Morning & Night
                    </button>
                    <button
                      type="button"
                      className="btn-secondary btn-sm"
                      onClick={() => handleApplyWindowPreset('afternoon')}
                      style={{ fontSize: 11, padding: '4px 8px' }}
                    >
                      ⚡ Afternoon Sprint
                    </button>
                    <button
                      type="button"
                      className="btn-secondary btn-sm"
                      onClick={() => handleApplyWindowPreset('full_academic')}
                      style={{ fontSize: 11, padding: '4px 8px' }}
                    >
                      🎯 Full Day Academic
                    </button>
                    <button
                      type="button"
                      className="btn-primary btn-sm"
                      onClick={() => setShowAddWindow(!showAddWindow)}
                      style={{ fontSize: 11, padding: '4px 10px', display: 'flex', alignItems: 'center', gap: 4 }}
                    >
                      <Plus size={12} /> {showAddWindow ? 'Close Form' : 'Add Window'}
                    </button>
                  </div>
                </div>

                {/* Inline Add Window Form */}
                {showAddWindow && (
                  <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', background: '#f8f6f0', padding: 12, borderRadius: 'var(--radius-sm)', border: '1px solid var(--line)', marginTop: 8 }}>
                    <div>
                      <label style={{ fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--muted)', display: 'block', marginBottom: 2 }}>From</label>
                      <input
                        type="time"
                        className="text-input"
                        style={{ padding: '4px 8px', fontSize: 12 }}
                        value={newWindowStart}
                        onChange={e => setNewWindowStart(e.target.value)}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--muted)', display: 'block', marginBottom: 2 }}>To</label>
                      <input
                        type="time"
                        className="text-input"
                        style={{ padding: '4px 8px', fontSize: 12 }}
                        value={newWindowEnd}
                        onChange={e => setNewWindowEnd(e.target.value)}
                      />
                    </div>
                    <div style={{ flex: 1, minWidth: 140 }}>
                      <label style={{ fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--muted)', display: 'block', marginBottom: 2 }}>Window Label</label>
                      <input
                        type="text"
                        className="text-input"
                        placeholder="e.g., Deep Focus"
                        style={{ width: '100%', padding: '4px 8px', fontSize: 12 }}
                        value={newWindowLabel}
                        onChange={e => setNewWindowLabel(e.target.value)}
                      />
                    </div>
                    <button
                      type="button"
                      className="btn-primary btn-sm"
                      style={{ alignSelf: 'flex-end', padding: '6px 14px' }}
                      onClick={handleAddFreeTimeWindow}
                    >
                      <Check size={12} /> Save Window
                    </button>
                  </div>
                )}

                {/* Reorderable Availability Window Cards (Ranked by Willingness) */}
                <div className="window-priority-list">
                  {freeTimeWindows.map((w, index) => {
                    const startM = parseTimeToMinutes(w.start);
                    let endM = parseTimeToMinutes(w.end);
                    if (endM <= startM) endM += 1440;
                    const count = Math.floor((endM - startM) / planSchedule.session_duration);
                    const isFirst = index === 0;
                    const isLast = index === freeTimeWindows.length - 1;
                    return (
                      <div key={w.id} className="window-priority-card">
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                          <span className="window-rank-badge">
                            #{index + 1} {isFirst ? 'Most Willing' : isLast && freeTimeWindows.length > 2 ? 'Least Willing' : 'Priority'}
                          </span>
                          <span style={{ fontWeight: 800, color: 'var(--ink)', fontSize: 13 }}>{w.label}</span>
                          <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--mint-dark)', fontWeight: 700 }}>
                            {formatMinutesToTime(startM)} – {formatMinutesToTime(endM)}
                          </span>
                          <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                            ({count} × {planSchedule.session_duration}m sessions)
                          </span>
                          {isFirst ? (
                            <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--coral)', background: 'rgba(239, 68, 68, 0.08)', padding: '2px 6px', borderRadius: 4 }}>
                              🔥 Receives Most Difficult Subjects
                            </span>
                          ) : (
                            <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--muted)', background: '#ede9df', padding: '2px 6px', borderRadius: 4 }}>
                              Reinforcement & Consolidation
                            </span>
                          )}
                        </div>
                        <div className="window-actions-group">
                          <button
                            type="button"
                            className="window-reorder-btn"
                            disabled={isFirst}
                            onClick={() => handleMoveWindowUp(index)}
                            title="Move window up (higher willingness to study difficult subjects)"
                            aria-label="Move window up"
                          >
                            <ArrowUp size={13} />
                          </button>
                          <button
                            type="button"
                            className="window-reorder-btn"
                            disabled={isLast}
                            onClick={() => handleMoveWindowDown(index)}
                            title="Move window down (lower willingness to study difficult subjects)"
                            aria-label="Move window down"
                          >
                            <ArrowDown size={13} />
                          </button>
                          <button
                            type="button"
                            className="window-reorder-btn"
                            onClick={() => handleRemoveFreeTimeWindow(w.id)}
                            style={{ color: 'var(--coral)' }}
                            title="Remove window"
                            aria-label="Remove window"
                          >
                            <X size={13} />
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Strips List Layout (Displayed One Below the Other, NOT Tiles) */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <h3 style={{ fontSize: 15, fontWeight: 800, color: 'var(--ink)' }}>
                  Study Schedule Strips
                </h3>
                <span className="badge badge-easy" style={{ fontSize: 10 }}>
                  {sessionLengthMode === 'ai_optimized' ? `🧠 AI Fixed (${planSchedule.session_duration}m Sessions)` : `🛠️ User Locked (${planSchedule.session_duration}m Sessions)`}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>
                  {completedTileIds.size} of {planSchedule.tiles?.length || 0} Sessions Completed
                </span>
                <button
                  type="button"
                  className="btn-secondary btn-sm"
                  style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, padding: '4px 10px' }}
                  onClick={handleRecreateSchedule}
                  disabled={isRecreatingSchedule}
                  title="Re-create and refresh your schedule at any time"
                >
                  <RefreshCw size={11} className={isRecreatingSchedule ? 'animate-spin' : ''} />
                  Re-create
                </button>
              </div>
            </div>

            {(!planSchedule.tiles || planSchedule.tiles.length === 0) ? (
              <div className="glass-card" style={{ padding: 32, textAlign: 'center', color: 'var(--muted)' }}>
                No study sessions scheduled. Add a free-time availability window above to generate sessions!
              </div>
            ) : (
              <div className="schedule-strips-list">
                {planSchedule.tiles.map((tile, idx) => {
                  const isDone = tile.is_completed;
                  return (
                    <div
                      key={tile.id}
                      className={`schedule-strip ${isDone ? 'completed' : ''}`}
                    >
                      {/* Left: Main Content (Time Slot, Subject, Recommended Topic) */}
                      <div className="strip-main-content">
                        {/* 1. Time Slot: Top left corner, in green bold font, NOT in a container */}
                        <div className="strip-time-slot">
                          {tile.time_slot_formatted || formatStripTimeSlot(tile.start_time, tile.end_time)}
                        </div>

                        {/* 2. Subject: Biggest font size in the strip, 2 sizes above recommended topic and time slot */}
                        <div className="strip-subject">
                          {tile.subject}
                        </div>

                        {/* 3. Recommended topic: In a color that's a darker shade of the background color */}
                        <div className="strip-recommended-topic">
                          <span className="strip-recommended-topic-label">Recommended topic:</span> {tile.target_topic}
                        </div>
                      </div>

                      {/* Right: Quick Actions & Metadata (Cognitive peak / night review removed) */}
                      <div className="strip-side-actions">
                        <div className="strip-meta-col">
                          <span style={{ fontSize: 11, fontWeight: 700, color: tile.concept_difficulty === 'Hard' ? 'var(--coral)' : tile.concept_difficulty === 'Medium' ? '#b45309' : 'var(--mint-dark)' }}>
                            {tile.concept_difficulty ? `${tile.concept_difficulty} Subject Topic` : 'Active Recall'}
                          </span>
                          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: tile.decay_p <= 0.70 ? 'var(--coral)' : 'var(--mint-dark)', fontWeight: 600 }}>
                            Retention: {Math.round(tile.decay_p * 100)}%
                          </span>
                        </div>
                        <button
                          type="button"
                          className="btn-primary btn-sm"
                          style={{ padding: '8px 14px', display: 'flex', alignItems: 'center', gap: 6 }}
                          onClick={() => startQuizSession(tile.subject, tile.target_concept_id)}
                          title={`Launch active recall quiz for ${tile.target_topic}`}
                        >
                          <Play size={12} /> Launch Quiz
                        </button>
                        <button
                          type="button"
                          className="btn-secondary btn-sm"
                          style={{
                            padding: '8px 12px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 5,
                            background: isDone ? 'var(--mint-bg)' : undefined,
                            borderColor: isDone ? 'var(--mint)' : undefined,
                            color: isDone ? 'var(--mint-dark)' : undefined
                          }}
                          onClick={() => handleToggleTileCompleted(tile.id)}
                          title="Toggle completion status"
                        >
                          <CheckCircle2 size={13} color={isDone ? 'var(--mint-dark)' : 'var(--muted)'} />
                          {isDone ? 'Completed' : 'Done'}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* 7-Day Full Adaptive Schedule & Memory Forecast (Card Deck) */}
            <div className="glass-card" style={{ marginTop: 28, padding: '24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12, marginBottom: 18 }}>
                <div>
                  <h3 style={{ fontSize: 16, fontWeight: 800, display: 'flex', alignItems: 'center', gap: 8, color: 'var(--ink)' }}>
                    <Calendar size={18} color="var(--mint-dark)" /> 7-Day Week-Full Plan & Decay Forecast
                  </h3>
                  <p style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>
                    Duolingo Half-Life Regression projection: concepts projected to cross below your {Math.round(settings.retention_threshold * 100)}% retention threshold.
                  </p>
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <button
                    className="btn-secondary btn-sm"
                    onClick={() => loadWeekPlan()}
                    title="Refresh 7-day memory forecast"
                    style={{ fontSize: 11, padding: '5px 10px' }}
                  >
                    <RefreshCw size={12} /> Sync Forecast
                  </button>
                </div>
              </div>

              {/* 7-Day Cards Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14 }}>
                {(() => {
                  const daysToRender = (weekPlan?.days && weekPlan.days.length === 7) ? weekPlan.days : Array.from({ length: 7 }).map((_, idx) => {
                    const dateObj = new Date();
                    dateObj.setDate(dateObj.getDate() + idx);
                    const isToday = idx === 0;
                    const isTmrw = idx === 1;
                    const displayTitle = isToday ? 'Today' : isTmrw ? 'Tomorrow' : dateObj.toLocaleDateString('en-US', { weekday: 'short' });
                    const formattedDate = dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                    const simulatedDue = concepts.filter(c => {
                      const projDelta = c.delta_days + idx;
                      const projP = calcRecallProb(c.half_life_days, projDelta);
                      return projP < settings.retention_threshold;
                    });
                    const urgency = simulatedDue.length > 3 ? 'critical' : simulatedDue.length > 0 ? 'warning' : 'optimal';
                    return {
                      day_offset: idx,
                      date: dateObj.toISOString().split('T')[0],
                      display_title: displayTitle,
                      formatted_date: formattedDate,
                      due_count: simulatedDue.length,
                      urgency_level: urgency,
                      planned_minutes: settings.daily_minutes,
                      subjects: [...new Set(simulatedDue.map(c => c.subject))],
                      concepts: simulatedDue.slice(0, 3)
                    };
                  });

                  return daysToRender.map((day) => {
                    const isCritical = day.urgency_level === 'critical';
                    const isWarning = day.urgency_level === 'warning';
                    const isToday = day.day_offset === 0;

                    let urgencyBadgeBg = 'var(--mint-bg)';
                    let urgencyBadgeColor = 'var(--mint-dark)';
                    let urgencyLabel = '🟢 Optimal';

                    if (isCritical) {
                      urgencyBadgeBg = 'var(--coral-bg)';
                      urgencyBadgeColor = 'var(--coral-dark)';
                      urgencyLabel = '🔴 Critical Decay';
                    } else if (isWarning) {
                      urgencyBadgeBg = 'var(--yellow-bg)';
                      urgencyBadgeColor = 'var(--yellow-dark)';
                      urgencyLabel = '🟡 Review Due';
                    }

                    return (
                      <div
                        key={day.day_offset}
                        style={{
                          background: isToday ? '#ffffff' : '#fcfbf8',
                          borderRadius: 'var(--radius-md)',
                          border: isToday ? '2px solid var(--mint-dark)' : isCritical ? '1.5px solid #df775d' : '1px solid var(--line)',
                          padding: '16px',
                          display: 'flex',
                          flexDirection: 'column',
                          justifyContent: 'space-between',
                          boxShadow: isToday ? '0 4px 14px rgba(50, 96, 78, 0.10)' : '0 1px 4px rgba(0,0,0,0.03)',
                          transition: 'transform 0.15s ease, box-shadow 0.15s ease'
                        }}
                      >
                        <div>
                          {/* Card Top: Title, Date, Urgency */}
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                            <div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <span style={{ fontSize: 15, fontWeight: 800, color: 'var(--ink)' }}>
                                  {day.display_title}
                                </span>
                                {isToday && (
                                  <span style={{ fontSize: 10, background: 'var(--mint-dark)', color: '#ffffff', padding: '1px 6px', borderRadius: 4, fontWeight: 700 }}>
                                    CURRENT
                                  </span>
                                )}
                              </div>
                              <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--muted)' }}>
                                {day.formatted_date}
                              </span>
                            </div>
                            <span
                              style={{
                                fontSize: 10,
                                fontWeight: 700,
                                background: urgencyBadgeBg,
                                color: urgencyBadgeColor,
                                padding: '3px 8px',
                                borderRadius: 12
                              }}
                            >
                              {urgencyLabel}
                            </span>
                          </div>

                          {/* Quick Stats: Target Time & Concepts Count */}
                          <div
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              padding: '8px 10px',
                              background: '#f4f1eb',
                              borderRadius: 'var(--radius-sm)',
                              fontSize: 11,
                              marginBottom: 12
                            }}
                          >
                            <span style={{ fontWeight: 600, color: 'var(--ink)' }}>
                              ⏱️ <b>{day.planned_minutes || settings.daily_minutes}m</b> Focus Target
                            </span>
                            <span style={{ fontWeight: 700, color: day.due_count > 0 ? 'var(--coral)' : 'var(--mint-dark)' }}>
                              📌 {day.due_count} Due
                            </span>
                          </div>

                          {/* Subject Focus Tags */}
                          {day.subjects && day.subjects.length > 0 && (
                            <div style={{ marginBottom: 12 }}>
                              <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 5 }}>
                                Subjects in Focus
                              </div>
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                                {day.subjects.map(s => (
                                  <span
                                    key={s}
                                    style={{
                                      fontSize: 10,
                                      padding: '2px 7px',
                                      borderRadius: 4,
                                      background: '#e9e6dd',
                                      color: 'var(--ink)',
                                      fontWeight: 600
                                    }}
                                  >
                                    {s}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Due Concepts Preview */}
                          <div style={{ marginBottom: 14 }}>
                            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 6 }}>
                              Projected Decaying Concepts
                            </div>
                            {day.concepts && day.concepts.length > 0 ? (
                              <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                                {day.concepts.map((c, cIdx) => (
                                  <div
                                    key={c.id || cIdx}
                                    style={{
                                      fontSize: 11,
                                      padding: '5px 8px',
                                      background: '#ffffff',
                                      border: '1px solid var(--line)',
                                      borderRadius: 'var(--radius-sm)',
                                      display: 'flex',
                                      justifyContent: 'space-between',
                                      alignItems: 'center'
                                    }}
                                  >
                                    <span style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }}>
                                      {c.name}
                                    </span>
                                    <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 700, color: (c.p_hat || 0.5) < 0.65 ? 'var(--coral)' : 'var(--mint-dark)' }}>
                                      {Math.round((c.p_hat || 0.5) * 100)}% recall
                                    </span>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <div style={{ fontSize: 11, color: 'var(--muted)', fontStyle: 'italic', padding: '6px 0' }}>
                                ✓ Memory retention optimal. No reviews overdue!
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Card Action */}
                        <button
                          className={isToday ? "btn-primary" : "btn-secondary"}
                          style={{ width: '100%', fontSize: 11, padding: '7px', justifyContent: 'center' }}
                          onClick={() => {
                            if (day.subjects?.[0]) {
                              startQuizSession(day.subjects[0]);
                            } else {
                              startQuizSession();
                            }
                          }}
                        >
                          <Zap size={12} /> {isToday ? "Start Today's Review Queue" : `Practice ${day.display_title}'s Focus`}
                        </button>
                      </div>
                    );
                  });
                })()}
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
                      setActiveTab('materials');
                    }}
                  >
                    <MessageSquare size={14} color="var(--mint-dark)" /> Discuss with AI Tutor
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


        {/* ================= SCREEN: MNEMONIC LAB & MEMORY ANCHORS ================= */}
        {activeTab === 'mnemonics' && (
          <div className="animate-fade-in" style={{ maxWidth: 940, margin: '0 auto' }}>
            <div className="section-header">
              <div>
                <h1 className="section-title">
                  <Sparkles size={18} /> AI Memory Anchor & Mnemonic Lab
                </h1>
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

        {/* ================= SCREEN 4: MATERIALS & AI TUTOR (NOTEBOOKLM WORKSPACE) ================= */}
        {activeTab === 'materials' && (
          <div className="animate-fade-in materials-ai-container">
            {/* 3-Column Grid: Left NotebookLM Sources Sidebar + Center Chatbot + Right Quiz Tile */}
            <div className="materials-ai-grid">
              {/* ================= LEFT COLUMN: NOTEBOOKLM SOURCES SIDEBAR ================= */}
              <div className="notebooklm-sidebar">
                {/* Sidebar Header: Subject Switcher */}
                <div className="notebooklm-sidebar-header">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <Database size={15} color="var(--mint-dark)" />
                      <span style={{ fontSize: 13, fontWeight: 800, color: 'var(--ink)' }}>Study Sources</span>
                    </div>
                    <span className="badge badge-medium" style={{ fontSize: 10 }}>
                      {subjectMaterials.length} Reference{subjectMaterials.length !== 1 ? 's' : ''}
                    </span>
                  </div>

                  {/* Subject Selection & Addition: Listed on the left as buttons */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <label style={{ fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>
                        Subjects
                      </label>
                      <button
                        type="button"
                        className="btn-secondary btn-sm"
                        style={{ padding: '3px 8px', fontSize: 11, display: 'inline-flex', alignItems: 'center', gap: 4 }}
                        onClick={() => setShowAddSubjectInput(prev => !prev)}
                        title="Add a new subject to study and upload materials for"
                      >
                        <Plus size={12} /> Add Subject
                      </button>
                    </div>

                    {/* Inline Add Subject Form */}
                    {showAddSubjectInput && (
                      <form
                        onSubmit={e => {
                          e.preventDefault();
                          handleAddNewSubject();
                        }}
                        style={{ display: 'flex', gap: 6, background: '#ffffff', padding: 6, borderRadius: 'var(--radius-sm)', border: '1px solid var(--line)' }}
                      >
                        <input
                          type="text"
                          className="text-input"
                          placeholder="Subject name..."
                          autoFocus
                          value={newSubjectName}
                          onChange={e => setNewSubjectName(e.target.value)}
                          style={{ flex: 1, padding: '4px 8px', fontSize: 11 }}
                        />
                        <button
                          type="submit"
                          className="btn-primary btn-sm"
                          style={{ padding: '4px 10px', fontSize: 11 }}
                          disabled={!newSubjectName.trim()}
                        >
                          Add
                        </button>
                        <button
                          type="button"
                          className="btn-secondary btn-sm"
                          onClick={() => {
                            setShowAddSubjectInput(false);
                            setNewSubjectName('');
                          }}
                          style={{ padding: '4px 6px' }}
                        >
                          <X size={12} />
                        </button>
                      </form>
                    )}

                    {/* Subjects List as Interactive Buttons */}
                    <div className="sidebar-subjects-list" style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 180, overflowY: 'auto' }}>
                      {subjectsList.map(subj => {
                        const isSelected = chatSubject.toLowerCase() === subj.toLowerCase();
                        const refCount = uploadedMaterials.filter(m => m.subject.toLowerCase() === subj.toLowerCase()).length;
                        return (
                          <button
                            key={subj}
                            type="button"
                            className={`subject-nav-btn ${isSelected ? 'active' : ''}`}
                            onClick={() => setChatSubject(subj)}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              padding: '7px 10px',
                              borderRadius: 'var(--radius-sm)',
                              border: isSelected ? '1px solid var(--mint-dark)' : '1px solid var(--line)',
                              background: isSelected ? 'var(--mint-bg)' : '#ffffff',
                              color: isSelected ? 'var(--mint-dark)' : 'var(--ink)',
                              fontWeight: isSelected ? 800 : 600,
                              fontSize: 12,
                              textAlign: 'left',
                              cursor: 'pointer',
                              transition: 'all 0.15s ease'
                            }}
                          >
                            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {subj}
                            </span>
                            <span
                              style={{
                                fontSize: 10,
                                fontFamily: 'var(--font-mono)',
                                padding: '1px 6px',
                                borderRadius: 10,
                                background: isSelected ? 'var(--mint-dark)' : '#f0ede6',
                                color: isSelected ? '#ffffff' : 'var(--muted)',
                                fontWeight: 700
                              }}
                            >
                              {refCount}
                            </span>
                          </button>
                        );
                      })}

                      {/* All Subjects Button */}
                      <button
                        type="button"
                        className={`subject-nav-btn ${chatSubject === 'All' ? 'active' : ''}`}
                        onClick={() => setChatSubject('All')}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '6px 10px',
                          borderRadius: 'var(--radius-sm)',
                          border: chatSubject === 'All' ? '1px solid var(--mint-dark)' : '1px dashed var(--line)',
                          background: chatSubject === 'All' ? 'var(--mint-bg)' : 'transparent',
                          color: chatSubject === 'All' ? 'var(--mint-dark)' : 'var(--muted)',
                          fontWeight: chatSubject === 'All' ? 800 : 500,
                          fontSize: 11,
                          textAlign: 'left',
                          cursor: 'pointer'
                        }}
                      >
                        <span>All Subjects (Combined)</span>
                        <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)' }}>
                          {uploadedMaterials.length}
                        </span>
                      </button>
                    </div>
                  </div>
                </div>

                {/* Sidebar Content (Scrollable): Upload Materials Box + Sources List */}
                <div className="notebooklm-sidebar-content">
                  {/* Dedicated "Upload Materials" Box */}
                  <div className="sidebar-upload-card">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: 12, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 5, color: 'var(--ink)' }}>
                        <Upload size={13} color="var(--mint-dark)" /> Upload Materials
                      </span>
                      <span style={{ fontSize: 10, color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>
                        PDF • DOCX • PPTX • TXT
                      </span>
                    </div>

                    {sidebarUploadSuccess && (
                      <div style={{ padding: '6px 10px', background: 'var(--mint-bg)', border: '1px solid #c2e2cf', borderRadius: 'var(--radius-sm)', color: 'var(--mint-dark)', fontSize: 11, fontWeight: 600 }}>
                        ✓ Source added & referenced by chatbot!
                      </div>
                    )}

                    {/* Textarea for pasting notes or text */}
                    <textarea
                      className="textarea-input"
                      rows={2}
                      style={{ padding: '8px 10px', fontSize: 11, resize: 'vertical' }}
                      placeholder="Paste syllabus, textbook excerpt, or notes here..."
                      value={sidebarUploadContent}
                      onChange={e => setSidebarUploadContent(e.target.value)}
                    />

                    {/* Drag & Drop File Zone */}
                    <div
                      className={`sidebar-drop-zone ${sidebarDragging ? 'drag-active' : ''}`}
                      onClick={() => sidebarFileInputRef.current?.click()}
                      onDragOver={e => { e.preventDefault(); setSidebarDragging(true); }}
                      onDragLeave={e => { e.preventDefault(); setSidebarDragging(false); }}
                      onDrop={e => {
                        e.preventDefault();
                        setSidebarDragging(false);
                        if (e.dataTransfer?.files?.[0]) {
                          handleSidebarProcessFile(e.dataTransfer.files[0]);
                        }
                      }}
                    >
                      <input
                        ref={sidebarFileInputRef}
                        type="file"
                        accept=".pdf,.docx,.doc,.pptx,.ppt,.txt,.md,.json"
                        style={{ display: 'none' }}
                        onChange={e => {
                          if (e.target.files?.[0]) {
                            handleSidebarProcessFile(e.target.files[0]);
                          }
                          e.target.value = '';
                        }}
                      />
                      {sidebarExtracting ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--mint-dark)', fontSize: 11 }}>
                          <RefreshCw size={13} className="animate-spin" /> Extracting document text...
                        </div>
                      ) : (
                        <>
                          <FileUp size={16} color="var(--mint-dark)" />
                          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink)' }}>
                            Attach PDF, DOCX, or PPT file
                          </span>
                          <span style={{ fontSize: 10, color: 'var(--muted)' }}>
                            Click to browse or drop file here
                          </span>
                        </>
                      )}
                    </div>

                    {/* Staged File Preview Chips */}
                    {sidebarStagedFiles.length > 0 && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                        {sidebarStagedFiles.map(f => (
                          <div key={f.id} className="staged-chip" style={{ width: '100%', justifyContent: 'space-between' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6, overflow: 'hidden' }}>
                              <span className={`file-type-badge ${f.fileType}`}>{f.fileType}</span>
                              <span style={{ fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 140 }}>
                                {f.name}
                              </span>
                            </div>
                            <button
                              type="button"
                              className="staged-chip-remove"
                              onClick={() => setSidebarStagedFiles(prev => prev.filter(x => x.id !== f.id))}
                            >
                              <X size={12} />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Submit Ingestion Button */}
                    <button
                      type="button"
                      className="btn-primary"
                      style={{ width: '100%', padding: '8px', fontSize: 12, justifyContent: 'center' }}
                      disabled={sidebarUploading || sidebarExtracting || (!sidebarUploadContent.trim() && sidebarStagedFiles.length === 0)}
                      onClick={handleSidebarUploadSubmit}
                    >
                      {sidebarUploading ? (
                        <><RefreshCw size={12} className="animate-spin" /> Adding Source...</>
                      ) : (
                        <><Sparkles size={12} /> Add to Sources & Ground AI</>
                      )}
                    </button>
                  </div>

                  {/* Sources List (NotebookLM Style) */}
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>
                        Referenced Sources ({subjectMaterials.length})
                      </span>
                      <span style={{ fontSize: 10, color: 'var(--mint-dark)', fontWeight: 600 }}>
                        ✓ All Active
                      </span>
                    </div>

                    {subjectMaterials.length === 0 ? (
                      <div style={{ padding: '16px 10px', textAlign: 'center', color: 'var(--muted)', fontSize: 12, border: '1px dashed var(--line)', borderRadius: 'var(--radius-sm)' }}>
                        No sources uploaded for {chatSubject} yet. Upload a PDF, DOCX, or notes above!
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                        {subjectMaterials.map(mat => {
                          let badgeType = 'text';
                          const lower = (mat.title || '').toLowerCase();
                          if (lower.endsWith('.pdf') || lower.includes('pdf')) badgeType = 'pdf';
                          else if (lower.endsWith('.docx') || lower.includes('docx') || lower.includes('word')) badgeType = 'docx';
                          else if (lower.endsWith('.pptx') || lower.endsWith('.ppt') || lower.includes('slides') || lower.includes('ppt')) badgeType = 'pptx';

                          return (
                            <div key={mat.id} className="sidebar-source-item">
                              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 6 }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 6, overflow: 'hidden' }}>
                                  <span className={`file-type-badge ${badgeType}`}>{badgeType}</span>
                                  <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', lineHeight: 1.3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                    {mat.title}
                                  </span>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                  <button
                                    type="button"
                                    className="btn-secondary btn-sm"
                                    style={{ padding: '2px 5px', fontSize: 10 }}
                                    title="Preview full source content"
                                    onClick={() => setSelectedSourcePreview(mat)}
                                  >
                                    View
                                  </button>
                                  <button
                                    type="button"
                                    className="staged-chip-remove"
                                    title="Remove source"
                                    onClick={() => handleDeleteMaterial(mat.id)}
                                  >
                                    <Trash2 size={12} color="var(--muted)" />
                                  </button>
                                </div>
                              </div>

                              <p style={{ fontSize: 11, color: 'var(--muted)', lineHeight: 1.4, margin: 0, maxHeight: 32, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                {mat.content}
                              </p>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* ================= CENTER COLUMN: THE CHATBOT ================= */}
              <div className="materials-chat-window">
                {/* Chatbot Header */}
                <div className="chat-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'var(--mint-bg)', border: '1px solid var(--mint)', display: 'grid', placeItems: 'center', color: 'var(--mint-dark)' }}>
                      <Bot size={18} />
                    </div>
                    <div>
                      <h3 style={{ fontSize: 14, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6, margin: 0 }}>
                        Subject Doubt Solver
                        <span
                          className={`badge ${geminiStatus?.healthy ? 'badge-easy' : 'badge-medium'}`}
                          style={{ fontSize: 10, display: 'inline-flex', alignItems: 'center', gap: 4 }}
                          title={geminiStatus?.healthy ? `Live Gemini Reasoning Active (${geminiStatus.model || 'gemini-flash'})` : 'Local Socratic Cognitive Engine Active'}
                        >
                          {geminiStatus?.healthy ? `✨ Gemini AI Online (${geminiStatus.model || 'Active'})` : '🧠 Cognitive Engine (Local)'}
                        </span>
                      </h3>
                      {!geminiStatus?.healthy && (
                        <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 2 }}>
                          Local Socratic heuristics active.{' '}
                          <button
                            onClick={() => setActiveTab('settings')}
                            style={{ color: 'var(--coral-dark)', textDecoration: 'underline', background: 'none', border: 'none', padding: 0, cursor: 'pointer', fontWeight: 600 }}
                          >
                            Configure API Key in Settings →
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Persona Selector & Reset */}
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                    <div className="persona-selector">
                      <button
                        className={`persona-pill ${chatPersona === 'socratic' ? 'active' : ''}`}
                        onClick={() => setChatPersona('socratic')}
                        title="Active recall tutor that asks guiding questions"
                      >
                        🧠 Socratic
                      </button>
                      <button
                        className={`persona-pill ${chatPersona === 'exam_prep' ? 'active' : ''}`}
                        onClick={() => setChatPersona('exam_prep')}
                        title="High-yield exam summaries and edge-cases"
                      >
                        🎯 Exam Prep
                      </button>
                      <button
                        className={`persona-pill ${chatPersona === 'eli5' ? 'active' : ''}`}
                        onClick={() => setChatPersona('eli5')}
                        title="Simple analogies with zero jargon"
                      >
                        💡 ELI5
                      </button>
                    </div>

                    <button
                      className="btn-secondary btn-sm"
                      onClick={() => setChatMessages([createDefaultConceptsMessage(chatSubject, concepts, uploadedMaterials)])}
                      title="Reset chat to default main concepts view"
                    >
                      <RotateCcw size={12} />
                    </button>
                  </div>
                </div>

                {/* Grounding Info Banner */}
                <div style={{ padding: '7px 14px', background: '#f5f9f6', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11, color: 'var(--mint-dark)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <FileCheck size={13} />
                    <span>Active Sources: <b>{subjectMaterials[0]?.title || `${chatSubject} Notes`}</b> ({subjectMaterials.length} files)</span>
                  </div>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--muted)' }}>
                    Referenced in all answers
                  </span>
                </div>

                {/* Chat Feed */}
                <div className="chat-feed" style={{ flex: 1, overflowY: 'auto' }}>
                  {chatMessages.map((msg, idx) => (
                    <div key={idx} className={`chat-msg-row ${msg.role === 'user' ? 'user' : 'ai'}`}>
                      <div className={`chat-avatar ${msg.role === 'user' ? 'user-av' : 'ai-av'}`}>
                        {msg.role === 'user' ? 'U' : <Bot size={15} />}
                      </div>
                      <div style={{ maxWidth: '85%' }}>
                        <div className={`chat-bubble ${msg.role === 'user' ? 'user' : 'ai'}`}>
                          <RenderFormattedChatMessage content={msg.content} />
                        </div>

                        <div className="chat-meta">
                          <span>{msg.timestamp}</span>
                          {msg.aiPowered ? (
                            <span style={{ color: 'var(--mint-dark)', fontWeight: 600 }}>• ✨ Gemini Grounded ({msg.model || 'Live'})</span>
                          ) : (
                            <span style={{ color: 'var(--muted)' }}>• Local Cognitive Engine</span>
                          )}
                          {msg.cited_materials && msg.cited_materials.length > 0 && (
                            <span style={{ color: 'var(--mint-dark)', background: 'var(--mint-bg)', padding: '1px 6px', borderRadius: 4, fontSize: 10 }}>
                              📚 Ref: {msg.cited_materials.join(', ')}
                            </span>
                          )}
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
                        <Bot size={15} />
                      </div>
                      <div className="chat-bubble ai" style={{ color: 'var(--muted)', fontStyle: 'italic', display: 'flex', alignItems: 'center', gap: 8 }}>
                        <RefreshCw size={13} className="animate-spin" /> Cross-referencing {chatSubject} sources & analyzing doubt...
                      </div>
                    </div>
                  )}
                </div>

                {/* WhatsApp / ChatGPT Style File Upload & Paste Window */}
                <div
                  className="modern-upload-paste-container"
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                >
                  {/* Drag & Drop Overlay */}
                  {isDragging && (
                    <div className="drop-overlay">
                      <FileUp size={28} />
                      <span style={{ fontWeight: 700, fontSize: 13 }}>Drop PDF, DOCX, or PPT File to Attach</span>
                      <span style={{ fontSize: 11, opacity: 0.85 }}>Text will be extracted automatically</span>
                    </div>
                  )}

                  {/* Staged File Attachments Bar */}
                  {stagedFiles.length > 0 && (
                    <div className="staged-files-list">
                      {stagedFiles.map(file => (
                        <div key={file.id} className="staged-chip">
                          <FileText size={14} color="var(--mint-dark)" />
                          <div style={{ display: 'flex', flexDirection: 'column' }}>
                            <span style={{ fontWeight: 600, maxWidth: 170, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {file.name}
                            </span>
                            <span style={{ fontSize: 10, color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>
                              {file.size} {file.pageCount > 1 ? `• ${file.pageCount} pages` : ''}
                            </span>
                          </div>
                          {file.status === 'extracting' ? (
                            <RefreshCw size={12} className="animate-spin" color="var(--mint-dark)" />
                          ) : (
                            <FileCheck size={12} color="var(--mint-dark)" />
                          )}
                          <button
                            type="button"
                            className="staged-chip-remove"
                            title="Remove attachment"
                            onClick={() => setStagedFiles(prev => prev.filter(f => f.id !== file.id))}
                          >
                            <X size={12} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Unified Prompt Input Textbox: Pin at left, Textarea in middle, Ask Doubt icon at right */}
                  <div className="input-actions-bar">
                    {/* Hidden File Input */}
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".pdf,.docx,.doc,.pptx,.ppt,.txt,.md,.json"
                      style={{ display: 'none' }}
                      onChange={e => {
                        if (e.target.files && e.target.files.length > 0) {
                          handleProcessFile(e.target.files[0]);
                        }
                        e.target.value = '';
                      }}
                    />

                    {/* Pin / Paperclip Icon Button at Left End */}
                    <button
                      type="button"
                      className="attach-btn"
                      onClick={() => fileInputRef.current?.click()}
                      title="Attach PDF, DOCX, or PPT file (or drag & drop anywhere here)"
                      disabled={extractingFile}
                    >
                      {extractingFile ? <RefreshCw size={15} className="animate-spin" /> : <Paperclip size={16} />}
                    </button>

                    {/* Textarea */}
                    <textarea
                      className="auto-expand-textarea"
                      rows={1}
                      placeholder={`Ask a doubt in ${chatSubject}, paste notes (Ctrl+V), or attach PDFs/DOCX/PPT...`}
                      value={chatInput}
                      disabled={chatLoading}
                      onChange={e => setChatInput(e.target.value)}
                      onPaste={handlePaste}
                      onKeyDown={e => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault();
                          handleSendChatMessage();
                        }
                      }}
                    />

                    {/* Quick Save to Materials Button if file or notes staged */}
                    {(stagedFiles.length > 0 || chatInput.trim().length > 30) && (
                      <button
                        type="button"
                        className="ingest-btn-pill"
                        onClick={() => handleIngestStagedMaterial()}
                        disabled={uploading}
                        title="Save this material to your permanent subject library and synthesize quiz questions"
                      >
                        <Sparkles size={11} />
                        {uploading ? 'Ingesting...' : 'Ingest'}
                      </button>
                    )}

                    {/* Ask Doubt Icon-Only Button at Right End */}
                    <button
                      type="button"
                      className="send-btn"
                      onClick={() => handleSendChatMessage()}
                      disabled={chatLoading || (!chatInput.trim() && stagedFiles.length === 0)}
                      title="Ask Doubt"
                    >
                      <Send size={15} />
                    </button>
                  </div>
                </div>
              </div>

              {/* ================= RIGHT COLUMN: QUIZ SECTION TILE ================= */}
              <div className="quiz-tile-column">
                <div
                  className="quiz-tile-card"
                  onClick={() => setShowQuizConfirm(true)}
                  title="Click to launch active recall quiz for this subject"
                >
                  <div className="quiz-tile-header">
                    <span className="badge badge-due" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                      <Zap size={11} /> Active Recall Mode
                    </span>
                    <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--mint-dark)', fontWeight: 700 }}>
                      HLR v2.0
                    </span>
                  </div>

                  <h3 style={{ fontSize: 16, fontWeight: 800, color: 'var(--ink)', marginBottom: 4 }}>
                    {chatSubject === 'All' ? 'All Subjects' : chatSubject} Quiz
                  </h3>
                  <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 12, lineHeight: 1.5 }}>
                    Test your understanding with questions synthesized directly from your uploaded materials.
                  </p>

                  {/* Recall & Due Metric Box */}
                  <div className="quiz-tile-metric-box">
                    <div>
                      <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--muted)', textTransform: 'uppercase' }}>
                        Recall Probability
                      </span>
                      <div style={{ fontSize: 18, fontWeight: 800, color: subjectRecall <= 70 ? 'var(--coral)' : 'var(--mint-dark)' }}>
                        {subjectRecall}%
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--muted)', textTransform: 'uppercase' }}>
                        Due Concepts
                      </span>
                      <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--ink)' }}>
                        {subjectDueCount} <span style={{ fontSize: 11, color: 'var(--muted)', fontWeight: 400 }}>/ {subjectConcepts.length}</span>
                      </div>
                    </div>
                  </div>

                  {/* Target Concept Previews */}
                  <div style={{ marginBottom: 14 }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink)', display: 'block', marginBottom: 6 }}>
                      Target Concepts:
                    </span>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                      {subjectConcepts.slice(0, 3).map((c, i) => (
                        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 8px', background: '#f8f6f0', borderRadius: 'var(--radius-sm)', fontSize: 11 }}>
                          <span style={{ fontWeight: 600, color: 'var(--ink)', maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {c.name}
                          </span>
                          <span style={{ fontFamily: 'var(--font-mono)', color: c.p_hat <= 0.70 ? 'var(--coral)' : 'var(--mint-dark)' }}>
                            {(c.p_hat * 100).toFixed(0)}%
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Launch Quiz Action Button */}
                  <button
                    type="button"
                    className="quiz-tile-action-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      setShowQuizConfirm(true);
                    }}
                  >
                    <Play size={14} /> Launch Quiz Session →
                  </button>
                </div>
              </div>
            </div>

            {/* ================= QUIZ CONFIRMATION MODAL ================= */}
            {showQuizConfirm && (
              <div className="modal-overlay" onClick={() => setShowQuizConfirm(false)}>
                <div className="confirm-modal-card" onClick={e => e.stopPropagation()}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
                    <div style={{ width: 44, height: 44, borderRadius: '50%', background: 'var(--yellow-bg)', display: 'grid', placeItems: 'center', color: 'var(--yellow-dark)' }}>
                      <Zap size={24} />
                    </div>
                    <div>
                      <h3 style={{ fontSize: 17, fontWeight: 800 }}>
                        Confirm Quiz Session
                      </h3>
                      <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                        {chatSubject === 'All' ? 'Comprehensive Review' : `${chatSubject} Focus`}
                      </span>
                    </div>
                  </div>

                  <p style={{ fontSize: 13, color: 'var(--ink)', lineHeight: 1.6, marginBottom: 14 }}>
                    You are about to start an active recall quiz session. Questions are dynamically generated from your uploaded notes and materials for <b>{chatSubject}</b>.
                  </p>

                  <div style={{ background: '#f8f6f0', border: '1px solid var(--line)', borderRadius: 'var(--radius-sm)', padding: 12, marginBottom: 16 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 6 }}>
                      Target Concepts in this Session:
                    </div>
                    <ul style={{ paddingLeft: 18, fontSize: 12, lineHeight: 1.5, color: 'var(--ink)' }}>
                      {subjectConcepts.slice(0, 4).map((c, i) => (
                        <li key={i}><b>{c.name}</b> (recall estimate: {(c.p_hat * 100).toFixed(0)}%)</li>
                      ))}
                    </ul>
                  </div>

                  <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 18, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Sparkles size={13} color="var(--mint-dark)" />
                    Settles & Meeder HLR will calibrate memory half-life based on your response time & correctness.
                  </div>

                  <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
                    <button
                      className="btn-secondary"
                      onClick={() => setShowQuizConfirm(false)}
                      style={{ padding: '9px 18px' }}
                    >
                      Cancel
                    </button>
                    <button
                      className="btn-primary"
                      onClick={() => {
                        setShowQuizConfirm(false);
                        startQuizSession(chatSubject === 'All' ? null : chatSubject);
                      }}
                      style={{ padding: '9px 22px', display: 'flex', alignItems: 'center', gap: 6 }}
                    >
                      <Play size={13} /> Confirm & Launch Quiz
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* ================= SOURCE DOCUMENT PREVIEW MODAL ================= */}
            {selectedSourcePreview && (
              <div className="modal-overlay" onClick={() => setSelectedSourcePreview(null)}>
                <div className="confirm-modal-card" style={{ maxWidth: 640, maxHeight: '85vh', display: 'flex', flexDirection: 'column' }} onClick={e => e.stopPropagation()}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                    <h3 style={{ fontSize: 16, fontWeight: 800, display: 'flex', alignItems: 'center', gap: 8 }}>
                      <FileText size={16} color="var(--mint-dark)" /> {selectedSourcePreview.title}
                    </h3>
                    <button className="btn-secondary btn-sm" onClick={() => setSelectedSourcePreview(null)}>
                      <X size={14} />
                    </button>
                  </div>

                  <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
                    <span className="badge badge-medium">{selectedSourcePreview.subject}</span>
                    <span className="badge badge-easy">✓ Active Source Context</span>
                  </div>

                  <div style={{ overflowY: 'auto', flex: 1, padding: 12, background: '#f8f6f0', border: '1px solid var(--line)', borderRadius: 'var(--radius-sm)', fontSize: 12, color: 'var(--ink)', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                    {selectedSourcePreview.content}
                  </div>

                  <div style={{ marginTop: 14, paddingTop: 10, borderTop: '1px solid var(--line)', display: 'flex', justifyContent: 'flex-end' }}>
                    <button className="btn-primary btn-sm" onClick={() => setSelectedSourcePreview(null)}>
                      Close
                    </button>
                  </div>
                </div>
              </div>
            )}
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
          <div className="animate-fade-in" style={{ maxWidth: 860, margin: '0 auto', paddingBottom: 40 }}>
            {/* Top Action Bar */}
            <div className="section-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
              <div>
                <h1 className="section-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Settings size={20} color="var(--mint-dark)" /> Planner Settings & HLR Model Engine
                </h1>
                <p style={{ fontSize: 13, color: 'var(--muted)', marginTop: 4 }}>
                  Configure your daily capacity, memory retention threshold, subject priorities, and Gemini AI.
                </p>
              </div>

              <button
                className="btn-primary"
                onClick={() => handleSaveSettings()}
                disabled={settingsSaving}
                style={{ padding: '9px 18px', display: 'flex', alignItems: 'center', gap: 7, fontSize: 13, fontWeight: 700 }}
              >
                {settingsSaving ? <RefreshCw size={14} className="animate-spin" /> : <Save size={14} />}
                {settingsSaving ? 'Saving Changes...' : 'Save All Settings'}
              </button>
            </div>

            {/* Save Success Toast */}
            {settingsSavedToast && (
              <div
                style={{
                  marginTop: 16,
                  padding: '10px 16px',
                  borderRadius: 'var(--radius-sm)',
                  background: 'var(--mint-bg)',
                  border: '1px solid #a5d5bf',
                  color: 'var(--mint-dark)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  fontSize: 13,
                  fontWeight: 700
                }}
              >
                <CheckCircle2 size={16} /> All planner settings and model parameters have been persisted to the backend!
              </div>
            )}

            {/* Card 1: Daily Study Capacity */}
            <div className="glass-card" style={{ marginTop: 20, marginBottom: 20 }}>
              <h3 style={{ fontSize: 15, fontWeight: 800, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 7, color: 'var(--ink)' }}>
                <Clock size={16} color="var(--mint-dark)" /> Daily Available Study Capacity
              </h3>
              <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 14 }}>
                Target study time allocated for daily review blocks. The planner dynamically balances your session slots across this capacity.
              </p>

              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
                {[20, 30, 45, 60, 90].map(mins => (
                  <button
                    key={mins}
                    type="button"
                    className={`btn-secondary ${settings.daily_minutes === mins ? 'btn-primary' : ''}`}
                    onClick={() => setSettings(prev => ({ ...prev, daily_minutes: mins }))}
                    style={{ padding: '8px 16px', fontWeight: 700, fontSize: 12 }}
                  >
                    {mins} mins
                  </button>
                ))}
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginLeft: 8 }}>
                  <span style={{ fontSize: 12, color: 'var(--muted)' }}>Custom:</span>
                  <input
                    type="number"
                    min="10"
                    max="360"
                    step="5"
                    value={settings.daily_minutes}
                    onChange={e => setSettings(prev => ({ ...prev, daily_minutes: Math.max(10, parseInt(e.target.value) || 30) }))}
                    className="text-input"
                    style={{ width: 75, padding: '6px 8px', fontSize: 12, textAlign: 'center' }}
                  />
                  <span style={{ fontSize: 12, color: 'var(--muted)' }}>min/day</span>
                </div>
              </div>
            </div>

            {/* Card 2: Target Retention Threshold */}
            <div className="glass-card" style={{ marginBottom: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <h3 style={{ fontSize: 15, fontWeight: 800, display: 'flex', alignItems: 'center', gap: 7, color: 'var(--ink)' }}>
                  <Brain size={16} color="var(--mint-dark)" /> Target Retention Threshold (R<sub>target</sub>)
                </h3>
                <span
                  style={{
                    fontSize: 14,
                    fontWeight: 800,
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--mint-dark)',
                    background: 'var(--mint-bg)',
                    padding: '3px 10px',
                    borderRadius: 12
                  }}
                >
                  {Math.round(settings.retention_threshold * 100)}% Recall Guarantee
                </span>
              </div>

              <div className="input-group">
                <input
                  type="range"
                  min="0.50"
                  max="0.90"
                  step="0.05"
                  className="range-input"
                  value={settings.retention_threshold}
                  onChange={e => setSettings(prev => ({ ...prev, retention_threshold: parseFloat(e.target.value) }))}
                  style={{ width: '100%', accentColor: 'var(--mint-dark)' }}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--muted)', marginTop: 4 }}>
                  <span>50% (High Velocity)</span>
                  <span>70% (Duolingo Optimal)</span>
                  <span>80% (High Retention)</span>
                  <span>90% (Exam Mastery)</span>
                </div>
                <p style={{ fontSize: 12, color: 'var(--muted)', marginTop: 8 }}>
                  Duolingo Half-Life Regression schedules concepts for review the moment recall probability drops below this threshold: <code>p = 2^(-Δ / h) &lt; R<sub>target</sub></code>.
                </p>
              </div>
            </div>

            {/* Card 3: Subject Management, Priorities & Exam Deadlines */}
            <div className="glass-card" style={{ marginBottom: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
                <div>
                  <h3 style={{ fontSize: 15, fontWeight: 800, display: 'flex', alignItems: 'center', gap: 7, color: 'var(--ink)' }}>
                    <Layers size={16} color="var(--mint-dark)" /> Subject Management & Priority Weighting
                  </h3>
                  <p style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
                    Adjust priority multipliers and upcoming exam dates. Higher priority subjects receive more frequent review slots.
                  </p>
                </div>
              </div>

              {/* Subject Rows */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {subjectsList.map(subj => {
                  const prio = settings.subject_priorities[subj] !== undefined ? settings.subject_priorities[subj] : 1.0;
                  const exam = settings.exam_dates[subj] || '';
                  const conceptCount = concepts.filter(c => c.subject.toLowerCase() === subj.toLowerCase()).length;

                  return (
                    <div
                      key={subj}
                      style={{
                        padding: '12px 14px',
                        background: '#ffffff',
                        border: '1px solid var(--line)',
                        borderRadius: 'var(--radius-sm)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 10
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontWeight: 800, fontSize: 13, color: 'var(--ink)' }}>{subj}</span>
                          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', padding: '2px 7px', background: '#f0ede6', borderRadius: 10, color: 'var(--muted)' }}>
                            {conceptCount} concepts
                          </span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <span style={{ fontSize: 11, color: 'var(--muted)' }}>Exam Date:</span>
                            <input
                              type="date"
                              className="text-input"
                              value={exam}
                              onChange={e => {
                                const updated = { ...settings.exam_dates, [subj]: e.target.value };
                                setSettings(prev => ({ ...prev, exam_dates: updated }));
                              }}
                              style={{ padding: '4px 8px', fontSize: 11, width: 130 }}
                            />
                          </div>
                          <button
                            type="button"
                            onClick={() => handleDeleteSubject(subj)}
                            style={{ color: 'var(--coral)', padding: '4px 8px', borderRadius: 4, display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, background: 'none', border: '1px solid transparent' }}
                            title={`Remove ${subj}`}
                          >
                            <Trash2 size={13} /> Remove
                          </button>
                        </div>
                      </div>

                      {/* Priority Slider */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <span style={{ fontSize: 11, color: 'var(--muted)', minWidth: 90 }}>
                          Priority: <b>{prio.toFixed(1)}x</b> {prio >= 1.5 ? '(High Focus)' : prio <= 0.8 ? '(Maintenance)' : '(Normal)'}
                        </span>
                        <input
                          type="range"
                          min="0.5"
                          max="2.0"
                          step="0.1"
                          value={prio}
                          onChange={e => {
                            const val = parseFloat(e.target.value);
                            setSettings(prev => ({
                              ...prev,
                              subject_priorities: { ...prev.subject_priorities, [subj]: val }
                            }));
                          }}
                          style={{ flex: 1, accentColor: 'var(--mint-dark)' }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Inline Add New Subject Form in Settings */}
              <div style={{ marginTop: 16, padding: '12px 14px', background: '#f8f6f0', borderRadius: 'var(--radius-sm)', border: '1px dashed var(--line)' }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', display: 'block', marginBottom: 8 }}>
                  + Add New Subject to Planner
                </span>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                  <input
                    type="text"
                    className="text-input"
                    placeholder="New subject name (e.g., Computer Networks, Physics)..."
                    value={newSubjectName}
                    onChange={e => setNewSubjectName(e.target.value)}
                    style={{ flex: 2, minWidth: 200, padding: '7px 10px', fontSize: 12 }}
                  />
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontSize: 11, color: 'var(--muted)' }}>Priority:</span>
                    <select
                      className="select-input"
                      value={newSubjectPriority}
                      onChange={e => setNewSubjectPriority(parseFloat(e.target.value))}
                      style={{ padding: '6px 8px', fontSize: 11 }}
                    >
                      <option value="0.8">0.8x (Low)</option>
                      <option value="1.0">1.0x (Normal)</option>
                      <option value="1.2">1.2x (Focused)</option>
                      <option value="1.5">1.5x (High Focus)</option>
                      <option value="2.0">2.0x (Exam Crunch)</option>
                    </select>
                  </div>
                  <button
                    type="button"
                    className="btn-primary btn-sm"
                    onClick={() => handleAddNewSubject()}
                    disabled={!newSubjectName.trim()}
                    style={{ padding: '7px 14px', fontSize: 12 }}
                  >
                    <Plus size={13} /> Add Subject
                  </button>
                </div>
              </div>
            </div>

            {/* Card 4: Gemini AI Engine Status & Diagnostics */}
            <div className="glass-card" style={{ marginBottom: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
                <div>
                  <h3 style={{ fontSize: 15, fontWeight: 800, display: 'flex', alignItems: 'center', gap: 7, color: 'var(--ink)' }}>
                    <Sparkles size={16} color="var(--mint-dark)" /> Google Gemini AI Model & Doubt Solver
                  </h3>
                  <p style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
                    API authentication is managed securely on the server via <code>backend/.env</code>.
                  </p>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span
                    className={`badge ${geminiStatus.healthy ? 'badge-easy' : 'badge-medium'}`}
                    style={{ fontSize: 11, display: 'flex', alignItems: 'center', gap: 5 }}
                  >
                    {geminiStatus.healthy ? <CheckCircle2 size={12} /> : <AlertTriangle size={12} />}
                    {geminiStatus.healthy ? `Active (${geminiStatus.model || 'Connected'})` : 'Cognitive Engine (Local)'}
                  </span>
                  <button
                    type="button"
                    className="btn-secondary btn-sm"
                    onClick={() => handleTestGeminiKey()}
                    disabled={geminiTesting}
                    style={{ padding: '6px 12px', fontSize: 11, display: 'flex', alignItems: 'center', gap: 5 }}
                    title="Ping backend to test Gemini connection status"
                  >
                    {geminiTesting ? <RefreshCw size={12} className="animate-spin" /> : <RefreshCw size={12} />}
                    {geminiTesting ? 'Testing...' : 'Test Connection'}
                  </button>
                </div>
              </div>

              {/* Status Banner */}
              <div
                style={{
                  padding: '12px 16px',
                  borderRadius: 'var(--radius-sm)',
                  background: geminiStatus.healthy ? 'var(--mint-bg)' : '#fbf6ea',
                  border: geminiStatus.healthy ? '1px solid #c2e2cf' : '1px solid #e7c86e',
                  fontSize: 12
                }}
              >
                <div style={{ fontWeight: 700, color: geminiStatus.healthy ? 'var(--mint-dark)' : 'var(--yellow-dark)', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                  {geminiStatus.healthy ? (
                    <>
                      <CheckCircle2 size={14} /> Connected to Google Gemini ({geminiStatus.model || 'gemini-3.5-flash-lite'})
                    </>
                  ) : (
                    <>
                      <AlertTriangle size={14} /> Local Cognitive Engine Active
                    </>
                  )}
                </div>
                <div style={{ color: 'var(--ink)', fontSize: 12, lineHeight: 1.5 }}>
                  {geminiStatus.healthy
                    ? `Live cloud reasoning is active using your environment key in backend/.env. Socratic doubt solving, grounding over uploaded sources, and flashcard generation are fully operational.`
                    : (geminiStatus.message || 'Operating in offline/local Socratic mode. Verify GEMINI_API_KEY in backend/.env to enable live cloud reasoning.')}
                </div>
              </div>
            </div>

            {/* Card 5: HLR Model Versions & Mathematical Spec */}
            <div className="glass-card">
              <h3 style={{ fontSize: 15, fontWeight: 800, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 7 }}>
                <Database size={15} color="var(--mint-dark)" /> HLR Model Versions & Feature Specifications
              </h3>
              <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 14 }}>
                Settles & Meeder (ACL 2016) formulation: Half-life <code>ĥ = 2^(Θ · X)</code>, where Θ represents the student difficulty weights and X represents attempt counts.
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div style={{ padding: 14, borderRadius: 'var(--radius-sm)', background: 'var(--mint-bg)', border: '1px solid #c2e2cf' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 800, color: 'var(--ink)', fontSize: 13 }}>Launch Model (Leitner Baseline)</span>
                    <span className="badge badge-easy">ACTIVE</span>
                  </div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--mint-dark)', marginTop: 4 }}>
                    Feature Spec: x = [1, n_right, n_wrong] | Weights Θ = [0.0, 1.0, -1.0]
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
                    Every correct answer doubles ĥ; every incorrect answer halves ĥ.
                  </div>
                </div>

                <div style={{ padding: 14, borderRadius: 'var(--radius-sm)', background: '#f0ede6', border: '1px solid var(--line)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 800, color: 'var(--muted)', fontSize: 13 }}>Trained Model (√Counts - Settles & Meeder)</span>
                    <span className="badge badge-medium">STAGING</span>
                  </div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>
                    Feature Spec: x = [1, √n_right, √n_wrong] | Weights Θ = [0.15, 1.42, -1.18]
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
                    Trained via AdaGrad gradient descent on student recall attempt logs.
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
              background: 'rgba(36, 49, 46, 0.45)',
              backdropFilter: 'blur(5px)',
              zIndex: 100,
              display: 'grid',
              placeItems: 'center',
              padding: 20
            }}
          >
            <div className="glass-card animate-fade-in" style={{ maxWidth: 540, width: '100%', padding: 28, background: '#ffffff', boxShadow: '0 12px 36px rgba(0,0,0,0.18)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <h3 style={{ fontSize: 18, fontWeight: 800, display: 'flex', alignItems: 'center', gap: 7 }}>
                  <Sliders size={18} color="var(--mint-dark)" /> FocusFlow Setup Wizard
                </h3>
                <button onClick={() => setShowOnboarding(false)} style={{ color: 'var(--muted)' }}>
                  <X size={18} />
                </button>
              </div>

              <p style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 18 }}>
                Configure your target subjects, study capacity, and retention goals to initialize your personal HLR adaptive schedule.
              </p>

              {/* Daily Available Study Time */}
              <div className="input-group" style={{ marginBottom: 18 }}>
                <label className="input-label" style={{ fontWeight: 700, fontSize: 12, marginBottom: 8, display: 'block' }}>
                  Daily Available Study Time
                </label>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {[20, 30, 45, 60, 90].map(mins => (
                    <button
                      key={mins}
                      type="button"
                      className={`btn-secondary ${settings.daily_minutes === mins ? 'btn-primary' : ''}`}
                      onClick={() => setSettings(prev => ({ ...prev, daily_minutes: mins }))}
                      style={{ flex: 1, minWidth: 60, padding: '8px 10px', fontSize: 12, fontWeight: 700 }}
                    >
                      {mins}m
                    </button>
                  ))}
                </div>
              </div>

              {/* Target Retention Goal */}
              <div className="input-group" style={{ marginBottom: 18 }}>
                <label className="input-label" style={{ fontWeight: 700, fontSize: 12, marginBottom: 8, display: 'block' }}>
                  Target Retention Guarantee (R<sub>target</sub>)
                </label>
                <div style={{ display: 'flex', gap: 6 }}>
                  {[
                    { val: 0.70, label: '70% Balanced' },
                    { val: 0.80, label: '80% High' },
                    { val: 0.85, label: '85% Exam Mastery' }
                  ].map(tier => (
                    <button
                      key={tier.val}
                      type="button"
                      className={`btn-secondary ${settings.retention_threshold === tier.val ? 'btn-primary' : ''}`}
                      onClick={() => setSettings(prev => ({ ...prev, retention_threshold: tier.val }))}
                      style={{ flex: 1, padding: '7px 8px', fontSize: 11, fontWeight: 600 }}
                    >
                      {tier.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Subjects to Track */}
              <div className="input-group" style={{ marginBottom: 18 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <label className="input-label" style={{ fontWeight: 700, fontSize: 12, margin: 0 }}>
                    Subjects to Track
                  </label>
                  <span style={{ fontSize: 11, color: 'var(--muted)' }}>Click to toggle</span>
                </div>

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
                  {subjectsList.map(subj => {
                    const isTracked = settings.subject_priorities[subj] !== undefined && settings.subject_priorities[subj] > 0;
                    return (
                      <button
                        key={subj}
                        type="button"
                        onClick={() => {
                          setSettings(prev => {
                            const updated = { ...prev.subject_priorities };
                            if (isTracked) {
                              updated[subj] = 0;
                            } else {
                              updated[subj] = 1.2;
                            }
                            return { ...prev, subject_priorities: updated };
                          });
                        }}
                        style={{
                          padding: '6px 12px',
                          borderRadius: 'var(--radius-full)',
                          fontSize: 12,
                          fontWeight: 600,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                          border: isTracked ? '1px solid var(--mint-dark)' : '1px solid var(--line)',
                          background: isTracked ? 'var(--mint-bg)' : '#f4f1eb',
                          color: isTracked ? 'var(--mint-dark)' : 'var(--muted)',
                          transition: 'all 0.15s ease'
                        }}
                      >
                        {isTracked ? <Check size={12} /> : <Plus size={12} />} {subj}
                      </button>
                    );
                  })}
                </div>

                {/* Inline mini add subject for wizard */}
                <div style={{ display: 'flex', gap: 6 }}>
                  <input
                    type="text"
                    className="text-input"
                    placeholder="Add custom subject..."
                    value={newSubjectName}
                    onChange={e => setNewSubjectName(e.target.value)}
                    style={{ flex: 1, padding: '6px 10px', fontSize: 11 }}
                  />
                  <button
                    type="button"
                    className="btn-secondary btn-sm"
                    disabled={!newSubjectName.trim()}
                    onClick={() => handleAddNewSubject()}
                    style={{ fontSize: 11, padding: '6px 12px' }}
                  >
                    + Add
                  </button>
                </div>
              </div>

              {/* Wizard Footer Actions */}
              <div style={{ marginTop: 24, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                <button className="btn-secondary" onClick={() => setShowOnboarding(false)} style={{ padding: '8px 16px', fontSize: 12 }}>
                  Close
                </button>
                <button
                  className="btn-primary"
                  onClick={async () => {
                    await handleSaveSettings();
                    await handleRecreateSchedule();
                    setShowOnboarding(false);
                    setActiveTab('plan');
                  }}
                  style={{ padding: '8px 20px', fontSize: 12, fontWeight: 700 }}
                >
                  <Sparkles size={13} /> Generate Adaptive Plan
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
