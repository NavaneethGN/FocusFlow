from fastapi import APIRouter
from app.schemas.schemas import (
    ChatRequest,
    ChatResponse,
    DoubtSolveRequest,
    DoubtSolveResponse,
    MnemonicRequest,
    MnemonicResponse,
)
from app.services.quiz_gen import test_gemini_connection, explain_concept_with_gemini
from app.services.ai_tutor import (
    chat_with_gemini,
    solve_doubt_with_gemini,
    generate_mnemonics_with_gemini,
)

router = APIRouter(prefix="/api/ai", tags=["ai_features"])


@router.get("/status")
async def get_ai_status():
    """Returns real-time status of the Gemini API configuration."""
    return await test_gemini_connection()


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """Interactive multi-turn conversation and doubt clearing with Socratic or Exam personas."""
    history_dicts = [{"role": m.role, "content": m.content} for m in req.history]

    # Gather materials context for the specified subject
    mats_text = req.materials_context or ""
    if not mats_text:
        try:
            import sys
            main_mod = sys.modules.get("main")
            if main_mod:
                matching = [
                    f"### Material: {m.get('title', 'Study Notes')}\n{m.get('content', '')}"
                    for m in getattr(main_mod, "db_materials", [])
                    if not req.subject or req.subject.lower() == "all" or m.get("subject", "").lower() == req.subject.lower()
                ]
                if matching:
                    mats_text = "\n\n".join(matching)
        except Exception:
            pass

    return await chat_with_gemini(
        message=req.message,
        history=history_dicts,
        subject=req.subject,
        persona=req.persona,
        concept_context=req.concept_context,
        materials_context=mats_text or None,
    )


@router.post("/solve-doubt", response_model=DoubtSolveResponse)
async def solve_doubt_endpoint(req: DoubtSolveRequest):
    """Step-by-step conceptual problem solver with pitfalls and verification."""
    return await solve_doubt_with_gemini(
        doubt=req.doubt,
        subject=req.subject,
        concept_context=req.concept_context,
        difficulty=req.difficulty,
    )


@router.post("/mnemonics", response_model=MnemonicResponse)
async def mnemonics_endpoint(req: MnemonicRequest):
    """Generates visual narrative mnemonics, real-world analogies, and interactive flashcards."""
    return await generate_mnemonics_with_gemini(
        concept_name=req.concept_name,
        topic=req.topic,
        subject=req.subject,
    )
