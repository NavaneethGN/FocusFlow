import json
import re
from typing import List, Dict, Any, Optional
import httpx
from app.core.config import settings


def sanitize_json(text: str) -> str:
    """Removes Markdown fences, trailing commas, and extracts valid JSON substring."""
    text = text.strip()
    # Strip markdown code blocks
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    # If surrounded by non-json text, extract bracketed structure
    array_match = re.search(r"(\[.*\])", text, flags=re.DOTALL)
    object_match = re.search(r"(\{.*\})", text, flags=re.DOTALL)
    
    if array_match and (not object_match or array_match.start() <= object_match.start()):
        return array_match.group(1).strip()
    elif object_match:
        return object_match.group(1).strip()
    return text


def extract_concepts_and_questions_fallback(title: str, text: str) -> List[Dict[str, Any]]:
    """Local robust semantic parser for notes when Gemini API key is not configured or offline.
    Extracts key concepts, definitions, and creates realistic multiple choice questions with explanations.
    """
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    concept_candidates = []
    
    for line in lines:
        match = re.match(r"^[\*\-\•]?\s*([A-Za-z0-9\s]{2,40})[:\-—]\s*(.+)$", line)
        if match:
            c_name = match.group(1).strip()
            c_desc = match.group(2).strip()
            concept_candidates.append((c_name, c_desc))
        elif len(line) > 20 and not line.startswith("#"):
            words = line.split()
            c_name = " ".join(words[:min(4, len(words))]).rstrip(":.-")
            concept_candidates.append((c_name, line))

    if not concept_candidates:
        concept_candidates.append((title, text[:300]))

    seen = set()
    unique_concepts = []
    for c_name, c_desc in concept_candidates:
        clean = c_name.lower()
        if clean not in seen and len(clean) > 2:
            seen.add(clean)
            unique_concepts.append((c_name, c_desc))
            if len(unique_concepts) >= 6:
                break

    results = []
    for name, desc in unique_concepts:
        q_text = f"Which statement best describes {name}?"
        correct_opt = desc if len(desc) < 140 else desc[:137] + "..."
        wrong_opt1 = f"It is an unrelated concept that opposes the principle of {name}."
        wrong_opt2 = f"It refers strictly to legacy systems with no impact on {name}."
        wrong_opt3 = f"A transient state that never produces measurable changes in {name}."
        
        options = [correct_opt, wrong_opt1, wrong_opt2, wrong_opt3]
        results.append({
            "name": name,
            "description": desc,
            "source": "local-heuristic",
            "questions": [
                {
                    "text": q_text,
                    "options": options,
                    "answer_index": 0,
                    "explanation": f"Based on the notes: '{desc}'",
                }
            ],
        })

    return results


SUPPORTED_GEMINI_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest",
    "gemini-3.8-flash",
    "gemini-pro-latest"
]


async def test_gemini_connection() -> Dict[str, Any]:
    """Tests if the configured Gemini API key is working by checking available models."""
    key = settings.get_gemini_api_key()
    if not key:
        return {"configured": False, "status": "missing_key", "message": "No GEMINI_API_KEY set. Configure it in Settings."}

    saw_quota_error = False
    last_error = ""

    for model in SUPPORTED_GEMINI_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        payload = {
            "contents": [{"parts": [{"text": "Reply with 'OK'"}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 10}
        }
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    return {
                        "configured": True,
                        "healthy": True,
                        "status": "connected",
                        "model": model,
                        "message": f"Successfully connected to Gemini API ({model})!"
                    }
                elif res.status_code == 429:
                    saw_quota_error = True
                    last_error = f"429 Quota exceeded on {model}"
                    continue
                elif res.status_code in (400, 403):
                    err_msg = res.json().get("error", {}).get("message", res.text)
                    return {"configured": True, "healthy": False, "status": "auth_error", "message": f"Gemini auth error: {err_msg}"}
                else:
                    last_error = f"{res.status_code} on {model}"
        except Exception as e:
            last_error = str(e)
            continue

    if saw_quota_error:
        return {
            "configured": True,
            "healthy": False,
            "status": "quota_exceeded",
            "message": "Gemini API key active, but daily free quota is exhausted on tested models. FocusFlow is operating with local cognitive heuristics."
        }

    return {
        "configured": True,
        "healthy": False,
        "status": "connection_error",
        "message": f"Could not connect to Gemini endpoints ({last_error}). Using local cognitive engine."
    }


async def generate_concepts_and_questions(title: str, content: str) -> List[Dict[str, Any]]:
    """Generates structured concepts and quiz questions from uploaded material using Gemini API,
    falling back to local heuristic extraction if unconfigured or offline.
    """
    key = settings.get_gemini_api_key()
    if key:
        prompt = f"""You are an elite educational AI and cognitive science tutor.
Analyze this study material and extract the 3 to 6 most critical concepts/principles.
For each concept, generate a high-yield multiple-choice question testing conceptual understanding.

Title: {title}
Study Material:
{content}

Respond with valid JSON matching this exact structure:
[
  {{
    "name": "Concept Name",
    "description": "Clear, concise 1-2 sentence explanation of the concept",
    "questions": [
      {{
        "text": "Thought-provoking multiple-choice question testing understanding?",
        "options": ["Correct answer", "Plausible distractor 1", "Plausible distractor 2", "Plausible distractor 3"],
        "answer_index": 0,
        "explanation": "Detailed explanation why the correct answer is right and key cognitive intuition"
      }}
    ]
  }}
]"""

        for model in SUPPORTED_GEMINI_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "response_mime_type": "application/json",
                    "temperature": 0.3
                }
            }
            try:
                async with httpx.AsyncClient(timeout=35.0) as client:
                    res = await client.post(url, json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                        clean_text = sanitize_json(raw_text)
                        parsed = json.loads(clean_text)
                        if isinstance(parsed, list) and len(parsed) > 0:
                            for item in parsed:
                                item["source"] = f"gemini ({model})"
                            return parsed
                    else:
                        print(f"Gemini API returned status {res.status_code}: {res.text[:200]}")
            except Exception as e:
                print(f"Gemini API error with model {model}: {e}")

    return extract_concepts_and_questions_fallback(title, content)


async def explain_concept_with_gemini(concept_name: str, topic: str, context: str = "") -> Dict[str, Any]:
    """Generates an intuitive, cognitive explanation with mnemonics and real-world analogies using Gemini."""
    key = settings.get_gemini_api_key()
    if key:
        prompt = f"""You are a master cognitive tutor specializing in spaced repetition and accelerated learning.
Explain the following concept to a university student:
Concept: {concept_name}
Topic / Domain: {topic}
Additional Context: {context}

Return valid JSON with these fields:
{{
  "summary": "Clear, 2-sentence executive summary",
  "intuition": "How to build an intuitive mental model for this concept",
  "mnemonic": "A memorable acronym, rhyme, or memory hook to retain this in long-term memory",
  "real_world_analogy": "A brilliant real-world analogy that makes the mechanism immediately obvious",
  "key_takeaways": [
    "Key takeaway point 1",
    "Key takeaway point 2",
    "Key takeaway point 3"
  ],
  "practice_question": {{
    "text": "A quick sanity-check question on this concept?",
    "options": ["Correct answer", "Distractor A", "Distractor B", "Distractor C"],
    "answer_index": 0,
    "explanation": "Brief explanation"
  }}
}}"""

        for model in SUPPORTED_GEMINI_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "response_mime_type": "application/json",
                    "temperature": 0.4
                }
            }
            try:
                async with httpx.AsyncClient(timeout=25.0) as client:
                    res = await client.post(url, json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                        clean_text = sanitize_json(raw_text)
                        parsed = json.loads(clean_text)
                        if isinstance(parsed, dict) and "summary" in parsed:
                            parsed["ai_powered"] = True
                            parsed["model"] = model
                            return parsed
            except Exception as e:
                print(f"Gemini explain error with {model}: {e}")

    # Fallback explanation
    return {
        "ai_powered": False,
        "model": "offline-heuristics",
        "summary": f"{concept_name} is a key concept in {topic} critical for exam readiness and conceptual mastery.",
        "intuition": f"Break {concept_name} down into its core inputs, internal state transformations, and observable outputs.",
        "mnemonic": f"Remember {concept_name[:3].upper()} — State, Transition, Output.",
        "real_world_analogy": "Think of it like a caching layer in a high-traffic system: it prevents repeated expensive lookups.",
        "key_takeaways": [
            f"Review {concept_name} spaced out across the forgetting curve.",
            "Test active recall instead of passive re-reading.",
            "Connect this concept to the broader systems architecture."
        ],
        "practice_question": {
            "text": f"What is the foundational requirement for {concept_name}?",
            "options": ["Maintaining consistent state across transitions", "Ignoring transient anomalies", "Manual batch verification", "Static memory bounds"],
            "answer_index": 0,
            "explanation": "Consistent state preservation is the core invariant."
        }
    }
