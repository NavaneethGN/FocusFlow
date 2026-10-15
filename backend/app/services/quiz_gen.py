import json
import re
from typing import List, Dict, Any
from app.core.config import settings


def extract_concepts_and_questions_fallback(title: str, text: str) -> List[Dict[str, Any]]:
    """Local robust semantic parser for notes when Gemini API key is not configured or offline.
    Extracts key concepts, definitions, and creates realistic multiple choice questions with explanations.
    """
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    results = []
    
    # Identify bullet points or sentences that look like definitions / key concepts
    concept_candidates = []
    for line in lines:
        # Check patterns like "Concept: explanation" or "Term - explanation"
        match = re.match(r"^[\*\-\•]?\s*([A-Za-z0-9\s]{2,40})[:\-—]\s*(.+)$", line)
        if match:
            c_name = match.group(1).strip()
            c_desc = match.group(2).strip()
            concept_candidates.append((c_name, c_desc))
        elif len(line) > 20 and not line.startswith("#"):
            # Use first few words as concept
            words = line.split()
            c_name = " ".join(words[:min(4, len(words))]).rstrip(":.-")
            concept_candidates.append((c_name, line))

    if not concept_candidates:
        # Fallback to title as concept
        concept_candidates.append((title, text[:300]))

    # Deduplicate and limit to top 6 concepts per upload
    seen = set()
    unique_concepts = []
    for c_name, c_desc in concept_candidates:
        clean = c_name.lower()
        if clean not in seen and len(clean) > 2:
            seen.add(clean)
            unique_concepts.append((c_name, c_desc))
            if len(unique_concepts) >= 6:
                break

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


async def generate_concepts_and_questions(title: str, content: str) -> List[Dict[str, Any]]:
    """Generates structured concepts and quiz questions from uploaded material.
    Uses Gemini structured JSON if GEMINI_API_KEY is configured, otherwise uses robust local extractor.
    """
    if settings.GEMINI_API_KEY:
        try:
            import httpx
            # Call Gemini generateContent API with structured JSON output
            prompt = f"""You are an educational AI. Extract key concepts and create multiple-choice questions from this study material.
Title: {title}
Content:
{content}

Return ONLY valid JSON matching this schema:
[
  {{
    "name": "Concept Name",
    "description": "Brief summary",
    "questions": [
      {{
        "text": "Question text?",
        "options": ["Correct answer", "Distractor 1", "Distractor 2", "Distractor 3"],
        "answer_index": 0,
        "explanation": "Why this answer is correct"
      }}
    ]
  }}
]"""
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.GEMINI_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"response_mime_type": "application/json"}
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(raw_text)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        return parsed
        except Exception as e:
            print(f"Gemini API call failed, falling back to local extractor: {e}")

    return extract_concepts_and_questions_fallback(title, content)
