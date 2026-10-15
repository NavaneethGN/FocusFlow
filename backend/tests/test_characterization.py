import json
import os
import re
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

import main
from tests import legacy_reference

client = TestClient(main.app)

SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "snapshots")
SNAPSHOT_FILE = os.path.join(SNAPSHOT_DIR, "characterization_scenario.json")
VECTORS_FILE = os.path.join(os.path.dirname(__file__), "hlr_test_vectors.json")

FIXED_TIME = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)

def test_characterization_scenario():
    """Module 0 Characterization Test with snapshotting under frozen clock."""
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    
    # Freeze clock and initialize DB
    main.set_clock(lambda: FIXED_TIME)
    try:
        main.init_db()

        # Step 1: Create a material / concept
        mat_resp = client.post("/api/materials", json={
            "subject": "Artificial Intelligence",
            "topic": "Reinforcement Learning",
            "title": "Q-Learning & Bellman Optimality",
            "content": "Q-learning is a model-free reinforcement learning algorithm to learn the value of an action in a particular state."
        })
        assert mat_resp.status_code == 200
        mat_data = mat_resp.json()
        new_concept_id = mat_data["concept"]["id"]

        # Step 2: Answer questions in a session
        ans1 = client.post("/api/sessions/sess-char-001/answers", headers={"X-Student-Id": "std-default"}, json={
            "event_id": "evt-char-001",
            "concept_id": "c-ai-1",
            "question_id": "q-1",
            "is_correct": True,
            "selected_index": 0,
            "response_time_ms": 1100
        })
        assert ans1.status_code == 200

        ans2 = client.post("/api/sessions/sess-char-001/answers", headers={"X-Student-Id": "std-default"}, json={
            "event_id": "evt-char-002",
            "concept_id": "c-ai-1",
            "question_id": "q-1",
            "is_correct": False,
            "selected_index": 1,
            "response_time_ms": 1400
        })
        assert ans2.status_code == 200

        # Step 3: Complete session
        comp_resp = client.post("/api/sessions/sess-char-001/complete")
        assert comp_resp.status_code == 200

        # Step 4: Fetch dashboard, plan, curve
        dash_resp = client.get("/api/dashboard")
        assert dash_resp.status_code == 200

        plan_resp = client.get("/api/plan/today")
        assert plan_resp.status_code == 200

        curve_resp = client.get("/api/concepts/c-ai-1/curve")
        assert curve_resp.status_code == 200

        # Mask dynamic generated concept id and question id for snapshot stability
        def sanitize_data(obj):
            if isinstance(obj, dict):
                clean = {}
                for k, v in obj.items():
                    if k in ("id", "concept_id") and isinstance(v, str) and (
                        (v.startswith("c-") and not re.match(r"^c-(ai|os|math|ds)-\d+$", v))
                        or (v.startswith("q-") and len(v) == 8)
                    ):
                        clean[k] = "<DYNAMIC_ID>"
                    else:
                        clean[k] = sanitize_data(v)
                return clean
            elif isinstance(obj, list):
                return [sanitize_data(x) for x in obj]
            return obj

        actual_scenario = {
            "materials_response": sanitize_data(mat_data),
            "answer1_response": ans1.json(),
            "answer2_response": ans2.json(),
            "complete_response": comp_resp.json(),
            "dashboard_response": sanitize_data(dash_resp.json()),
            "plan_response": sanitize_data(plan_resp.json()),
            "curve_response": curve_resp.json()
        }

        if not os.path.exists(SNAPSHOT_FILE):
            with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
                json.dump(actual_scenario, f, indent=2, sort_keys=True)
            print("Created characterization snapshot.")

        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            expected_scenario = json.load(f)

        assert actual_scenario == expected_scenario
    finally:
        main.reset_clock()
        main.init_db()

def test_hlr_python_against_test_vectors():
    """Verify legacy_reference and main HLR math against shared test vectors."""
    assert os.path.exists(VECTORS_FILE), f"Missing test vectors: {VECTORS_FILE}"
    with open(VECTORS_FILE, "r", encoding="utf-8") as f:
        vectors = json.load(f)

    assert len(vectors) >= 40, f"Expected at least 40 vectors, found {len(vectors)}"

    for idx, vec in enumerate(vectors):
        theta = vec["theta"]
        x = vec["x"]
        delta = vec["delta_days"]
        th = vec["threshold"]

        # Legacy reference
        h_ref = legacy_reference.half_life(theta, x)
        p_ref = legacy_reference.recall_prob(h_ref, delta)
        rev_ref = legacy_reference.next_review_days(h_ref, th)

        # Main implementation
        h_main = main.half_life(theta, x)
        p_main = main.recall_prob(h_main, delta)
        rev_main = main.next_review_days(h_main, th)

        assert abs(h_ref - vec["half_life"]) <= 1e-12, f"Vector {idx} legacy h mismatch"
        assert abs(p_ref - vec["recall"]) <= 1e-12, f"Vector {idx} legacy recall mismatch"
        assert abs(rev_ref - vec["next_review_days"]) <= 1e-12, f"Vector {idx} legacy review mismatch"

        assert abs(h_main - vec["half_life"]) <= 1e-12, f"Vector {idx} main h mismatch"
        assert abs(p_main - vec["recall"]) <= 1e-12, f"Vector {idx} main recall mismatch"
        assert abs(rev_main - vec["next_review_days"]) <= 1e-12, f"Vector {idx} main review mismatch"

def test_negative_delta_legacy_clamping():
    """Negative delta is clamped to 0 in legacy implementation."""
    h = 4.0
    p_neg = main.recall_prob(h, -5.0)
    p_zero = main.recall_prob(h, 0.0)
    assert p_neg == p_zero
    assert p_neg == 0.9999

def test_models_metrics_guard():
    """Guard test: no model metric may be a fabricated number."""
    resp = client.get("/api/models")
    assert resp.status_code == 200
    data = resp.json()

    assert "models" in data
    for model in data["models"]:
        assert "loss_metric" not in model, "Misleading loss_metric must be removed"
        assert "auc" not in model, "Misleading auc must be removed"
        assert model.get("metrics") is None, f"Model {model.get('id')} has non-null metrics"

    active_models = [m for m in data["models"] if m.get("active")]
    assert len(active_models) == 1
    assert active_models[0]["status"] == "provisional_fixed_weights"

def test_no_fabricated_metrics_in_source():
    """Ensure fake metric strings 0.124, 0.089, 0.812 do not appear in source code."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    forbidden = ["0." + "124", "0." + "089", "0." + "812"]

    scanned_exts = (".py", ".js", ".jsx", ".ts", ".tsx")
    ignore_dirs = {".git", "node_modules", ".venv", "__pycache__", "snapshots", "tests"}

    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for f in files:
            if f.endswith(scanned_exts):
                file_path = os.path.join(root, f)
                with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
                    for string_val in forbidden:
                        assert string_val not in content, f"Found forbidden string {string_val} in {file_path}"
