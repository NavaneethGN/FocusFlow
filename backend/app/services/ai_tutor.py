import json
import re
from typing import List, Dict, Any, Optional
import httpx
from app.core.config import settings
from app.services.quiz_gen import sanitize_json

GEMINI_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest",
    "gemini-3.8-flash",
    "gemini-pro-latest",
]


async def chat_with_gemini(
    message: str,
    history: List[Dict[str, str]],
    subject: Optional[str] = None,
    persona: str = "socratic",
    concept_context: Optional[str] = None,
    materials_context: Optional[str] = None,
) -> Dict[str, Any]:
    """Interactive multi-turn conversation and doubt clearing with Socratic/Exam persona using Gemini."""
    key = settings.get_gemini_api_key()

    persona_prompts = {
        "socratic": (
            "You are FocusFlow's Socratic Study Buddy and Doubt Solver. Your mission is to resolve student doubts "
            "by explaining the core intuition, referring directly to their uploaded study materials, and guiding them with "
            "thoughtful questions. Be concise, warm, and encourage active recall. Keep responses under 220 words."
        ),
        "exam_prep": (
            "You are FocusFlow's High-Yield Exam Coach and Doubt Solver. Clear doubts with crisp, structured bullet points, "
            "essential invariants/formulas, edge cases, and highlight exactly how professors or interviewers test these concepts from the materials."
        ),
        "eli5": (
            "You are FocusFlow's 'Explain Like I'm 5' Master. Deconstruct the student's doubt using delightful, real-world metaphors "
            "grounded in their study materials with zero academic pretension."
        ),
    }

    system_instruction = persona_prompts.get(persona, persona_prompts["socratic"])
    context_str = f" Subject: {subject}." if subject else ""
    if concept_context:
        context_str += f" Related Concept: {concept_context}."
    if materials_context:
        context_str += (
            f"\n\n--- UPLOADED STUDY MATERIALS (SOURCE OF TRUTH) ---\n"
            f"{materials_context[:4500]}\n"
            f"--- END OF STUDY MATERIALS ---\n"
            f"CRITICAL INSTRUCTION: Clear the student's doubts by directly referring to and explaining the contents "
            f"of these uploaded materials. Quote or reference specific sections where relevant to ground your explanation."
        )

    if key:
        # Build multi-turn contents
        contents = []
        first_user_text = f"[System Context: {system_instruction}{context_str}]\n\n"

        for i, turn in enumerate(history[-8:]):  # Keep recent context window
            role = "model" if turn.get("role") in ("model", "assistant") else "user"
            text = turn.get("content", "")
            if i == 0 and role == "user":
                text = first_user_text + text
            contents.append({"role": role, "parts": [{"text": text}]})

        # Add current message
        current_text = message if contents else (first_user_text + message)
        contents.append({"role": "user", "parts": [{"text": current_text}]})

        # Ask for response and followups
        structured_prompt = (
            f"\n\n[Format requirement: Answer the question naturally in Markdown. "
            f"At the very end of your reply, on a new line, add: "
            f"SUGGESTED_FOLLOWUPS: Follow-up question 1 | Follow-up question 2 | Follow-up question 3]"
        )
        contents[-1]["parts"][0]["text"] += structured_prompt

        for model in GEMINI_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            payload = {
                "contents": contents,
                "generationConfig": {
                    "temperature": 0.5 if persona == "socratic" else 0.2,
                    "maxOutputTokens": 700,
                },
            }
            try:
                async with httpx.AsyncClient(timeout=12.0) as client:
                    res = await client.post(url, json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        raw_reply = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                        
                        followups = []
                        if "SUGGESTED_FOLLOWUPS:" in raw_reply:
                            parts = raw_reply.split("SUGGESTED_FOLLOWUPS:")
                            main_reply = parts[0].strip()
                            followups = [q.strip() for q in parts[1].split("|") if q.strip()]
                        else:
                            main_reply = raw_reply

                        if not followups:
                            followups = [
                                f"How does this relate to the rest of {subject or 'my notes'}?",
                                "What is the common mistake students make here?",
                                "Can you test my understanding with an active recall question?",
                            ]

                        return {
                            "reply": main_reply,
                            "persona": persona,
                            "ai_powered": True,
                            "model": model,
                            "suggested_followups": followups[:3],
                            "cited_materials": [subject] if subject else ["General Study Notes"],
                        }
                    elif res.status_code in (429, 404):
                        print(f"Gemini API returned status {res.status_code} on {model}. Trying next model...")
                        continue
                    elif res.status_code in (400, 403):
                        print(f"Gemini API auth error ({res.status_code}).")
                        break
            except Exception as e:
                print(f"Chat error with {model}: {e}")
                continue

    # Offline / missing key or quota fallback
    subject_label = subject or "this topic"
    meta_keywords = [
        "capabilities", "what can you do", "who are you", "what are your features",
        "how does this work", "help me understand focusflow", "hello", "hi", "how are you"
    ]
    is_meta = any(k in message.lower() for k in meta_keywords)

    if is_meta:
        meta_reply = (
            "### FocusFlow Subject Doubt Solver & AI Study Buddy\n\n"
            "Here are my core capabilities to help you master any subject and achieve long-term memory retention:\n\n"
            "1. **Socratic Doubt Solving:** I deconstruct tricky doubts into foundational mental models, guiding you through thoughtful active recall questions rather than passive spoon-feeding.\n"
            "2. **Grounded Source Analysis:** Upload course notes, lecture slides, or textbook excerpts (`PDF`, `DOCX`, `PPTX`, `TXT`) in the left panel. I directly reference your specific materials to answer doubts.\n"
            "3. **Adaptive Personas:**\n"
            "   - **Socratic:** Deep conceptual intuition & guided questions.\n"
            "   - **Exam Prep:** High-yield exam bullet points, common traps, and formulas.\n"
            "   - **ELI5:** Delightful, intuitive real-world metaphors with zero pretension.\n"
            "4. **Duolingo Half-Life Regression (HLR) Math:** Every review session updates your memory half-life ($h = 2^{\\theta x}$) and recall probability ($p = 2^{-\\Delta / h}$) to schedule study sessions right before memory decays.\n\n"
            "*Ask any conceptual doubt about your subjects, paste notes, or select a topic from the sidebar to begin!*"
        )
        return {
            "reply": meta_reply,
            "persona": persona,
            "ai_powered": False,
            "model": "local-cognitive-engine",
            "suggested_followups": [
                f"Quiz me on {subject_label}",
                "Can you explain the Half-Life Regression formula?",
                "What is a real-world software engineering analogy for this?"
            ],
            "cited_materials": [subject] if subject else ["FocusFlow System Knowledge"]
        }

    if materials_context:
        clean_excerpt = materials_context.replace("### Material:", "").strip()
        first_lines = "\n".join(clean_excerpt.splitlines()[:5]).strip()
        fallback_replies = {
            "socratic": (
                f"Regarding your doubt on **{subject_label}**, let's inspect the underlying mechanism in your study material:\n\n"
                f"> *\"{first_lines[:260]}...\"*\n\n"
                f"**Cognitive Intuition:** In **{subject_label}**, the primary mechanism maintains consistency by enforcing invariant state boundaries. "
                f"When addressing *'{message.strip('?')}'*, observe how the system handles transition edge cases. "
                f"What do you predict would happen if this boundary constraint were violated during execution?"
            ),
            "exam_prep": (
                f"### High-Yield Doubt Resolution ({subject_label})\n"
                f"- **From Study Sources:** *\"{first_lines[:180]}...\"*\n"
                f"- **Key Takeaway:** For *{message[:40]}*, always articulate the underlying invariant and boundary conditions first.\n"
                f"- **Exam Pitfall:** Conflating temporary transient failure with persistent partition decay.\n"
                f"- **HLR Anchor:** Retention decays exponentially as $p = 2^{{-\\Delta / h}}$, so immediate targeted quiz review cements this principle."
            ),
            "eli5": (
                f"Think of your notes on **{subject_label}** like a clear instruction manual! "
                f"It points out: *\"{first_lines[:150]}...\"*\n\n"
                f"In simple terms, it's just like having guardrails on a bridge so nothing falls over the edge no matter how busy traffic gets!"
            ),
        }
    else:
        fallback_replies = {
            "socratic": (
                f"That's a thoughtful question regarding **{subject_label}**! Let's examine it: "
                f"If you consider how **{message.strip('?')}** impacts memory and state, "
                f"what is the primary variable that changes? "
                f"Consider what happens when elapsed time $\\Delta$ increases along the Ebbinghaus curve—"
                f"does recall probability decay linearly or exponentially?"
            ),
            "exam_prep": (
                f"### High-Yield Exam Summary: {subject_label}\n"
                f"- **Core Concept:** When asked about *{message[:40]}...*, examiners want to see the underlying invariant.\n"
                f"- **Formula/Mechanism:** $p = 2^{{-\\Delta / h}}$ where $h$ is half-life and $\\Delta$ is elapsed time.\n"
                f"- **Exam Tip:** Watch out for boundary conditions (e.g. $\\Delta = 0 \\implies p = 1.0$; $\\Delta = h \\implies p = 0.5$)."
            ),
            "eli5": (
                f"Imagine you have a mental bucket with water. Every day, half of the water evaporates unless you top it off! "
                f"When you asked about **{message[:35]}...**, think of it like putting a tighter lid on the bucket so knowledge stays inside longer."
            ),
        }

    return {
        "reply": fallback_replies.get(persona, fallback_replies["socratic"]),
        "persona": persona,
        "ai_powered": False,
        "model": "local-cognitive-engine",
        "suggested_followups": [
            f"Quiz me on {subject_label}",
            "Can you explain the formula step-by-step?",
            "What is a real-world engineering example?",
        ],
        "cited_materials": [subject] if subject else ["General Study Notes"],
    }


async def solve_doubt_with_gemini(
    doubt: str,
    subject: str = "General",
    concept_context: Optional[str] = None,
    difficulty: str = "Medium",
) -> Dict[str, Any]:
    """Provides a pedagogical step-by-step resolution with intuition, pitfalls, and verification challenge."""
    key = settings.get_gemini_api_key()

    if key:
        prompt = f"""You are a top computer science and mathematics professor.
A student has asked this specific doubt:
Doubt: "{doubt}"
Subject / Context: {subject} {f'({concept_context})' if concept_context else ''}
Difficulty Level: {difficulty}

Provide a structured pedagogical resolution. Return strictly valid JSON:
{{
  "core_intuition": "Explain the underlying concept in 2-3 crystal clear sentences without overwhelming math or jargon.",
  "step_by_step_solution": [
    "Step 1: Identify given constraints and foundational principles",
    "Step 2: Trace the logic or apply mathematical derivation",
    "Step 3: Arrive at conclusion and explain the 'why'"
  ],
  "common_pitfalls": [
    "Mistake 1 that causes students to fail exam questions on this",
    "Mistake 2: Confusing this with a similar concept"
  ],
  "retention_hook": "A memorable 1-sentence rule-of-thumb, mnemonic, or mental model to never forget this.",
  "verification_challenge": {{
    "question": "A quick multiple-choice question to test if the student truly understood this answer",
    "options": ["Correct option", "Common misconception A", "Distractor B", "Distractor C"],
    "answer_index": 0,
    "explanation": "Why the correct option holds true."
  }}
}}"""

        for model in GEMINI_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "response_mime_type": "application/json",
                    "temperature": 0.2,
                },
            }
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    res = await client.post(url, json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                        clean_text = sanitize_json(raw_text)
                        parsed = json.loads(clean_text)
                        if isinstance(parsed, dict) and "core_intuition" in parsed:
                            parsed["doubt"] = doubt
                            parsed["subject"] = subject
                            parsed["ai_powered"] = True
                            parsed["model"] = model
                            return parsed
                    elif res.status_code in (429, 404):
                        print(f"Gemini API returned status {res.status_code} in doubt solver on {model}. Trying next...")
                        continue
                    elif res.status_code in (400, 403):
                        print(f"Gemini API auth error in doubt solver ({res.status_code}).")
                        break
            except Exception as e:
                print(f"Doubt solve error with {model}: {e}")
                continue

    # Fallback Doubt Resolution
    return {
        "doubt": doubt,
        "subject": subject,
        "core_intuition": f"The doubt regarding '{doubt[:60]}...' centers on understanding the invariant state transitions in {subject}. Rather than memorizing the outcome, look at what remains constant across operations.",
        "step_by_step_solution": [
            f"Step 1: Frame the question within {subject} foundational axioms.",
            f"Step 2: Deconstruct inputs, transforms, and edge boundary conditions.",
            "Step 3: Apply the half-life rule: active recall reinforces the synaptic pathways required for this specific logic.",
        ],
        "common_pitfalls": [
            "Conflating theoretical asymptotic bounds with practical implementation overhead.",
            "Assuming memory decays linearly rather than exponentially according to Ebbinghaus forgetting curve.",
        ],
        "retention_hook": "Invariant Check: State before + applied operation = verified post-condition.",
        "verification_challenge": {
            "question": f"In the context of '{doubt[:50]}...', what is the primary indicator of correctness?",
            "options": [
                "Satisfying system invariants under all edge conditions",
                "Maximizing throughput without verifying consistency",
                "Skipping validation for faster execution",
                "Hardcoding fixed response timeouts",
            ],
            "answer_index": 0,
            "explanation": "Invariants must hold true before and after state transitions to guarantee correctness.",
        },
        "ai_powered": False,
        "model": "offline-solver",
    }


async def generate_mnemonics_with_gemini(
    concept_name: str,
    topic: Optional[str] = "",
    subject: Optional[str] = "General",
) -> Dict[str, Any]:
    """Generates visual narrative mnemonics, real-world metaphors, and active recall flashcards."""
    key = settings.get_gemini_api_key()

    if key:
        prompt = f"""You are a world-class memory athlete and neuro-educator using spaced repetition.
Create vivid memory anchors and interactive flashcards for:
Concept: "{concept_name}"
Topic: "{topic}"
Subject: "{subject}"

Return strictly valid JSON:
{{
  "story_mnemonic": "A vivid, bizarre, or humorous mental story / picture that makes this concept instantly memorable.",
  "acronym_or_rhyme": "A clever acronym, rhyme, or catchphrase.",
  "real_world_metaphor": "A brilliant everyday analogy (e.g. how a restaurant, airport, or car uses this exact principle).",
  "key_takeaway": "The one critical sentence to remember for exams.",
  "flashcards": [
    {{
      "front": "Active recall question 1 (testing core definition)",
      "back": "Precise, intuitive answer",
      "hint": "Subtle memory clue"
    }},
    {{
      "front": "Active recall question 2 (testing edge-case or mechanism)",
      "back": "Precise, intuitive answer",
      "hint": "Subtle memory clue"
    }},
    {{
      "front": "Active recall question 3 (testing 'why it matters')",
      "back": "Precise, intuitive answer",
      "hint": "Subtle memory clue"
    }}
  ]
}}"""

        for model in GEMINI_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "response_mime_type": "application/json",
                    "temperature": 0.4,
                },
            }
            try:
                async with httpx.AsyncClient(timeout=25.0) as client:
                    res = await client.post(url, json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                        clean_text = sanitize_json(raw_text)
                        parsed = json.loads(clean_text)
                        if isinstance(parsed, dict) and "story_mnemonic" in parsed:
                            parsed["concept_name"] = concept_name
                            parsed["subject"] = subject or "General"
                            parsed["ai_powered"] = True
                            parsed["model"] = model
                            return parsed
            except Exception as e:
                print(f"Mnemonic error with {model}: {e}")

    # Fallback Mnemonics
    acronym = "".join([w[0].upper() for w in concept_name.split() if w[:1].isalpha()])[:4] or "MEM"
    return {
        "concept_name": concept_name,
        "subject": subject or "General",
        "story_mnemonic": f"Picture a glowing neon sign for '{concept_name}'. Whenever a request arrives, a diligent librarian checks the index and instantly routes it to the exact shelf without scanning every book.",
        "acronym_or_rhyme": f"Remember {acronym}: Active Retrieval Maximizes Half-life!",
        "real_world_metaphor": f"Think of {concept_name} like an airport baggage carousel: items are indexed, tracked, and retrieved in deterministic order.",
        "key_takeaway": f"Mastering {concept_name} anchors your retention in {subject} and prevents recall decay.",
        "flashcards": [
            {
                "front": f"What is the primary role of {concept_name}?",
                "back": f"It establishes the key mechanism for {topic or subject} and ensures deterministic behavior.",
                "hint": "Think about stability and predictability.",
            },
            {
                "front": f"When elapsed time equals half-life (Δ = h), what is the recall probability for {concept_name}?",
                "back": "50% (0.50). This is the definition of memory half-life in Settles & Meeder (2016).",
                "hint": "2^(-1)",
            },
            {
                "front": f"Why is active testing superior to re-reading for {concept_name}?",
                "back": "Active retrieval forces synaptic pathway reconstruction, which statistically doubles the estimated half-life h.",
                "hint": "Testing effect.",
            },
        ],
        "ai_powered": False,
        "model": "offline-mnemonic-lab",
    }
