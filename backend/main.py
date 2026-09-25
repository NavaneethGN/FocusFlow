from datetime import date, datetime
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

Difficulty = Literal["Easy", "Medium", "Hard"]
Status = Literal["Planned", "In progress", "Missed", "Completed"]


class Task(BaseModel):
    id: int | None = None
    subject: str = Field(min_length=1, max_length=60)
    deadline_days: int = Field(ge=1, le=30)
    difficulty: Difficulty
    status: Status = "Planned"


class TimeSlot(BaseModel):
    day: int = Field(ge=0, le=30)
    start: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class ScheduleRequest(BaseModel):
    tasks: list[Task] = Field(min_length=1)
    available_slots: list[TimeSlot] = Field(min_length=1)
    locked_schedule: list["ScheduleItem"] = Field(default_factory=list)


class ScheduleItem(BaseModel):
    day: int
    time: str
    subject: str
    start: str
    end: str
    priority: float
    difficulty: Difficulty
    status: Status


class ScheduleResponse(BaseModel):
    generated_on: str
    total_slots: int
    scheduled_slots: int
    completion_percent: int
    schedule: list[ScheduleItem]
    priority_order: list[str]


app = FastAPI(title="Study Planner API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def priority(task: Task) -> float:
    difficulty_weight = {"Easy": 1, "Medium": 2, "Hard": 3}[task.difficulty]
    urgency = 12 / task.deadline_days
    adaptive_boost = 3 if task.status == "Missed" else 0
    return round(urgency + (difficulty_weight * 1.8) + adaptive_boost, 2)


def build_schedule(request: ScheduleRequest) -> ScheduleResponse:
    locked = list(request.locked_schedule)
    completed_subjects = {
        item.subject for item in locked if item.status == "Completed"
    }
    ranked = sorted(
            [task for task in request.tasks if task.status != "Completed" and task.subject not in completed_subjects],
        key=priority,
        reverse=True,
    )
    output: list[ScheduleItem] = []
    assignment_counts = {task.subject: 0 for task in ranked}
    for slot in sorted(request.available_slots, key=lambda item: (item.day, item.start)):
        eligible = [task for task in ranked if task.deadline_days >= slot.day + 1]
        if not eligible:
            continue
        task = min(
            eligible,
            key=lambda candidate: (-priority(candidate), assignment_counts[candidate.subject]),
        )
        assignment_counts[task.subject] += 1
        output.append(
            ScheduleItem(
                day=slot.day,
                time=f"{slot.start}-{slot.end}",
                subject=task.subject,
                start=slot.start,
                end=slot.end,
                priority=priority(task),
                difficulty=task.difficulty,
                status=task.status,
            )
        )

    output = locked + output
    scheduled_slots = len(output)
    total_slots = len(request.available_slots)
    completion_percent = min(100, round((scheduled_slots / total_slots) * 100)) if total_slots else 0
    return ScheduleResponse(
        generated_on=date.today().isoformat(),
        total_slots=total_slots,
        scheduled_slots=scheduled_slots,
        completion_percent=completion_percent,
        schedule=output,
        priority_order=[task.subject for task in ranked],
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/schedule", response_model=ScheduleResponse)
def create_schedule(request: ScheduleRequest) -> ScheduleResponse:
    return build_schedule(request)
