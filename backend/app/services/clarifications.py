from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
import re
from uuid import uuid4

from pydantic import ValidationError

from app.schemas import (
    ClarificationDecision,
    ClarificationQuestion,
    ClarificationStatus,
    ClarificationSummary,
    ClarificationUpdateRequest,
    DatasetClarifications,
    FindingReference,
    FindingType,
    InspectionFinding,
)

CLARIFICATION_DIRECTORY_NAME = "clarifications"
CLARIFICATION_FILE_NAME = "questions.json"
EMAIL_IN_TEXT_PATTERN = re.compile(
    r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+"
    r"(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+"
)
AMBIGUOUS_FINDING_TYPES = {
    FindingType.MISSING_VALUES,
    FindingType.DUPLICATE_IDENTIFIER_VALUES,
    FindingType.MISSING_REFERENCE,
    FindingType.SUSPICIOUS_NUMERIC_VALUES,
    FindingType.PROBABLE_PERSONAL_DATA,
}


class ClarificationError(RuntimeError):
    """Raised when clarification state cannot be stored safely."""


class ClarificationQuestionNotFoundError(LookupError):
    """Raised when a response targets a question outside the current findings."""


def get_dataset_clarifications(
    workspace_directory: str | Path,
    *,
    dataset_id: str,
    findings: list[InspectionFinding],
    use_snapshot: bool = True,
) -> DatasetClarifications:
    """Generate questions, optionally merging the compatibility snapshot."""
    workspace = Path(workspace_directory).resolve()
    stored = (
        _read_clarifications(workspace, dataset_id=dataset_id)
        if use_snapshot
        else None
    )
    stored_by_id = {
        question.question_id: question
        for question in stored.questions
    } if stored else {}

    questions: list[ClarificationQuestion] = []
    for finding in findings:
        if finding.type not in AMBIGUOUS_FINDING_TYPES:
            continue
        generated = _question_for_finding(finding)
        previous = stored_by_id.get(generated.question_id)
        if previous:
            generated = generated.model_copy(
                update={
                    "answer": previous.answer,
                    "status": previous.status,
                    "updated_at": previous.updated_at,
                }
            )
        questions.append(generated)

    result = _build_response(dataset_id, questions)
    if use_snapshot and (stored is None or stored != result):
        _write_clarifications(workspace, result)
    return result


def update_dataset_clarification(
    workspace_directory: str | Path,
    *,
    dataset_id: str,
    findings: list[InspectionFinding],
    question_id: str,
    update: ClarificationUpdateRequest,
    persist: bool = True,
    use_snapshot: bool = True,
) -> DatasetClarifications:
    """Prepare one human answer or deferral and optionally store its snapshot."""
    workspace = Path(workspace_directory).resolve()
    current = get_dataset_clarifications(
        workspace,
        dataset_id=dataset_id,
        findings=findings,
        use_snapshot=use_snapshot,
    )
    matching = next(
        (question for question in current.questions if question.question_id == question_id),
        None,
    )
    if matching is None:
        raise ClarificationQuestionNotFoundError(
            "Clarification question was not found for this dataset."
        )

    if update.decision == ClarificationDecision.ANSWER:
        answer = _safe_answer(update.answer or "")
        replacement = matching.model_copy(
            update={
                "answer": answer,
                "status": ClarificationStatus.ANSWERED,
                "updated_at": datetime.now(timezone.utc),
            }
        )
    else:
        replacement = matching.model_copy(
            update={
                "answer": None,
                "status": ClarificationStatus.DEFERRED,
                "updated_at": datetime.now(timezone.utc),
            }
        )

    questions = [
        replacement if question.question_id == question_id else question
        for question in current.questions
    ]
    result = _build_response(dataset_id, questions)
    if persist:
        _write_clarifications(workspace, result)
    return result


def store_dataset_clarifications(
    workspace_directory: str | Path,
    clarifications: DatasetClarifications,
) -> None:
    """Best-effort mirror of PostgreSQL clarification state for compatibility."""
    try:
        _write_clarifications(Path(workspace_directory).resolve(), clarifications)
    except ClarificationError:
        # PostgreSQL is authoritative. Snapshot failures must not invalidate a
        # response whose workflow mutation and audit event already committed.
        pass


def _question_for_finding(finding: InspectionFinding) -> ClarificationQuestion:
    location = _finding_location(finding)
    if finding.type == FindingType.MISSING_REFERENCE:
        question = (
            f"How should participant identifiers in {location} that do not match "
            "the participant file be handled: corrected, supplied, or documented "
            "as intentional exclusions?"
        )
        why = "Research context is required to distinguish data errors from valid exclusions."
    elif finding.type == FindingType.DUPLICATE_IDENTIFIER_VALUES:
        question = (
            f"Should values in {location} be unique? If yes, which source or "
            "record-selection rule determines the authoritative record?"
        )
        why = "Choosing between duplicate identifiers can discard or merge valid records."
    elif finding.type == FindingType.SUSPICIOUS_NUMERIC_VALUES:
        question = (
            f"Do the flagged numeric values in {location} represent valid measurements, "
            "missing-value sentinels, or data-entry errors? State their intended meaning "
            "and approved handling."
        )
        why = "Numeric extremes cannot be changed safely without their unit and coding convention."
    elif finding.type == FindingType.MISSING_VALUES:
        question = (
            f"Are the missing entries in {location} expected? State why they are missing "
            "and whether they should remain blank, use a documented code, or be resolved "
            "from an authoritative source."
        )
        why = "Missingness may be meaningful and should not be imputed or recoded by assumption."
    else:
        category = finding.evidence.get("category", "personal data")
        question = (
            f"Is the probable {str(category).replace('_', ' ')} in {location} required "
            "for the shared dataset? State the approved access, retention, or "
            "de-identification handling."
        )
        why = (
            "Pattern and column-name signals are probable privacy indicators, not confirmed "
            "legal classifications."
        )

    return ClarificationQuestion(
        question_id=_question_id(finding),
        related_finding=FindingReference(
            type=finding.type,
            file=finding.file,
            affected_column=finding.affected_column,
        ),
        question=question,
        why_this_matters=why,
        status=ClarificationStatus.UNANSWERED,
    )


def _question_id(finding: InspectionFinding) -> str:
    identity = "|".join(
        [finding.type.value, finding.file, finding.affected_column or "<file>"]
    )
    return f"cq_{sha256(identity.encode('utf-8')).hexdigest()[:20]}"


def _finding_location(finding: InspectionFinding) -> str:
    return (
        f"{finding.file} / {finding.affected_column}"
        if finding.affected_column
        else finding.file
    )


def _build_response(
    dataset_id: str,
    questions: list[ClarificationQuestion],
) -> DatasetClarifications:
    answered = sum(
        question.status == ClarificationStatus.ANSWERED for question in questions
    )
    deferred = sum(
        question.status == ClarificationStatus.DEFERRED for question in questions
    )
    unanswered = sum(
        question.status == ClarificationStatus.UNANSWERED for question in questions
    )
    return DatasetClarifications(
        dataset_id=dataset_id,
        summary=ClarificationSummary(
            total_count=len(questions),
            answered_count=answered,
            deferred_count=deferred,
            unanswered_count=unanswered,
        ),
        questions=questions,
    )


def _read_clarifications(
    workspace: Path,
    *,
    dataset_id: str,
) -> DatasetClarifications | None:
    path = workspace / CLARIFICATION_DIRECTORY_NAME / CLARIFICATION_FILE_NAME
    if not path.exists():
        return None
    try:
        result = DatasetClarifications.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValidationError) as exc:
        raise ClarificationError("Dataset clarification state is unavailable or invalid.") from exc
    if result.dataset_id != dataset_id:
        raise ClarificationError("Dataset clarification state does not match the workspace.")
    return result


def _write_clarifications(
    workspace: Path,
    clarifications: DatasetClarifications,
) -> None:
    directory = workspace / CLARIFICATION_DIRECTORY_NAME
    destination = directory / CLARIFICATION_FILE_NAME
    temporary = directory / f".{CLARIFICATION_FILE_NAME}.{uuid4().hex}.tmp"
    payload = clarifications.model_dump_json(indent=2) + "\n"
    try:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            view = memoryview(payload.encode("utf-8"))
            while view:
                written = os.write(descriptor, view)
                if written == 0:
                    raise OSError("Clarification write made no progress.")
                view = view[written:]
        finally:
            os.close(descriptor)
        temporary.replace(destination)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise ClarificationError("Dataset clarification state could not be stored.") from exc


def _safe_answer(answer: str) -> str:
    normalized = " ".join(answer.split())
    masked = EMAIL_IN_TEXT_PATTERN.sub("[masked-email]", normalized)
    if not masked:
        raise ClarificationError("A clarification answer cannot be empty.")
    return masked[:2_000]
