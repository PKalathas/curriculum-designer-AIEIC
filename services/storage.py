"""Storage abstraction for Curriculum Designer drafts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from threading import Lock
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from config import settings
from models.curriculum import FeedbackEntry, LabMaterial, QuizQuestion, Rubric
from services.database import (
    CourseRecord,
    CurriculumDraftRecord,
    EventRecord,
    LabRecord,
    build_engine,
    create_session_factory,
    ensure_schema,
)


class CurriculumStore(ABC):
    """Abstract base. All implementations must be safe for concurrent calls."""

    @abstractmethod
    def get(self, lab_id: str) -> LabMaterial | None: ...

    @abstractmethod
    def put(self, material: LabMaterial) -> None: ...

    @abstractmethod
    def list(self) -> list[LabMaterial]: ...

    @abstractmethod
    def delete(self, lab_id: str) -> bool: ...

    def record_event(
        self,
        *,
        event_type: str,
        material: LabMaterial,
        actor_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Optional audit hook; memory store intentionally ignores events."""


class MemoryStore(CurriculumStore):
    """In-memory dict-backed store. Good enough for v0.1 + tests."""

    def __init__(self) -> None:
        self._data: dict[str, LabMaterial] = {}
        self._lock = Lock()

    def get(self, lab_id: str) -> LabMaterial | None:
        with self._lock:
            return self._data.get(lab_id)

    def put(self, material: LabMaterial) -> None:
        with self._lock:
            self._data[material.lab_id] = material

    def list(self) -> list[LabMaterial]:
        with self._lock:
            return list(self._data.values())

    def delete(self, lab_id: str) -> bool:
        with self._lock:
            return self._data.pop(lab_id, None) is not None


class PostgresCurriculumStore(CurriculumStore):
    """Postgres-backed store for editable curriculum drafts."""

    def __init__(self, database_url: str) -> None:
        self._engine = build_engine(database_url)
        ensure_schema(self._engine)
        self._session_factory = create_session_factory(self._engine)

    def get(self, lab_id: str) -> LabMaterial | None:
        with self._session_factory() as session:
            row = session.get(CurriculumDraftRecord, lab_id)
            if row is None:
                return None
            return _row_to_material(row)

    def put(self, material: LabMaterial) -> None:
        with self._session_factory() as session:
            _upsert_course_and_lab(session, material)
            row = session.get(CurriculumDraftRecord, material.lab_id)
            values = _material_to_values(material)
            if row is None:
                row = CurriculumDraftRecord(**values)
                session.add(row)
            else:
                for key, value in values.items():
                    setattr(row, key, value)
            session.commit()

    def list(self) -> list[LabMaterial]:
        with self._session_factory() as session:
            rows = session.scalars(select(CurriculumDraftRecord).order_by(CurriculumDraftRecord.lab_id)).all()
            return [_row_to_material(row) for row in rows]

    def delete(self, lab_id: str) -> bool:
        with self._session_factory() as session:
            row = session.get(CurriculumDraftRecord, lab_id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True

    def record_event(
        self,
        *,
        event_type: str,
        material: LabMaterial,
        actor_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        with self._session_factory() as session:
            session.add(
                EventRecord(
                    event_id=str(uuid4()),
                    event_type=event_type,
                    course_id=material.course_id,
                    lab_id=material.lab_id,
                    source="curriculum-designer",
                    actor_type="instructor" if actor_id else None,
                    actor_id=actor_id,
                    payload_json={
                        "version": material.version,
                        "approval_status": material.approval_status,
                        **(payload or {}),
                    },
                    occurred_at=datetime.now(timezone.utc),
                )
            )
            session.commit()


def _upsert_course_and_lab(session, material: LabMaterial) -> None:
    course = session.get(CourseRecord, material.course_id)
    if course is None:
        session.add(CourseRecord(course_id=material.course_id, title=material.course_id))

    lab = session.get(LabRecord, material.lab_id)
    if lab is None:
        session.add(
            LabRecord(
                lab_id=material.lab_id,
                course_id=material.course_id,
                title=material.title,
                phase="pre_lab",
            )
        )
    else:
        lab.course_id = material.course_id
        lab.title = material.title
        lab.updated_at = datetime.now(timezone.utc)


def _material_to_values(material: LabMaterial) -> dict[str, Any]:
    return {
        "lab_id": material.lab_id,
        "course_id": material.course_id,
        "title": material.title,
        "spec_markdown": material.spec_markdown,
        "quiz_json": [q.model_dump(mode="json") for q in material.quiz],
        "rubric_json": material.rubric.model_dump(mode="json"),
        "learning_objectives_json": list(material.learning_objectives),
        "difficulty": material.difficulty,
        "estimated_duration_min": material.estimated_duration_min,
        "material_content": material.material_content,
        "agent_instructions": material.agent_instructions,
        "approval_status": material.approval_status,
        "approved_by": material.approved_by,
        "approval_notes": material.approval_notes,
        "feedback_history_json": [entry.model_dump(mode="json") for entry in material.feedback_history],
        "version": material.version,
        "generated_at": material.generated_at,
        "last_updated": material.last_updated,
    }


def _row_to_material(row: CurriculumDraftRecord) -> LabMaterial:
    return LabMaterial(
        lab_id=row.lab_id,
        course_id=row.course_id,
        title=row.title,
        spec_markdown=row.spec_markdown,
        quiz=[QuizQuestion(**item) for item in row.quiz_json],
        rubric=Rubric(**row.rubric_json),
        learning_objectives=list(row.learning_objectives_json or []),
        difficulty=row.difficulty,
        estimated_duration_min=row.estimated_duration_min,
        material_content=row.material_content,
        agent_instructions=row.agent_instructions,
        approval_status=row.approval_status,
        approved_by=row.approved_by,
        approval_notes=row.approval_notes,
        feedback_history=[FeedbackEntry(**item) for item in row.feedback_history_json],
        version=row.version,
        generated_at=row.generated_at,
        last_updated=row.last_updated,
    )


def build_store(backend: str) -> CurriculumStore:
    """Factory called from main.py during lifespan."""
    backend = backend.lower()
    if backend == "memory":
        return MemoryStore()
    if backend == "postgres":
        return PostgresCurriculumStore(settings.database_url)
    raise ValueError(f"Unknown storage backend: {backend!r}")
