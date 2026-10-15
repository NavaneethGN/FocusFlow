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
    """Interactive multi-turn conversation with Socratic or Exam personas."""
    history_dicts = [{"role": m.role, "content": m.content} for m in req.history]
    return await chat_with_gemini(
        message=req.message,
        history=history_dicts,
        subject=req.subject,
        persona=req.persona,
        concept_context=req.concept_context,
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
