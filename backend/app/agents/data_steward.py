import os

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.exceptions import AgentRunError, UserError
from pydantic_ai.models import Model

from app.api_errors import AIConfigurationError, AIServiceError
from app.schemas import (
    ClarificationStatus,
    DatasetClarifications,
    DatasetInspection,
    DatasetSummary,
    FindingReference,
    FindingSeverity,
    FindingType,
    InspectionFinding,
    ReadinessSummary,
    RecommendationResponse,
)

DATAQUAY_AI_MODEL_ENV = "DATAQUAY_AI_MODEL"
PRIVACY_EVIDENCE_KEYS = {
    "category",
    "occurrence_count",
    "detection_methods",
    "masked_evidence",
}
AGENT_INSTRUCTIONS = """
You are the DataQuay Data Steward Agent. Turn deterministic dataset findings into
concise remediation recommendations for a human data steward.

Use only the supplied dataset summary, readiness result, and masked findings.
Do not infer or request raw dataset rows. Never claim that an action was applied,
approved, or completed. You can only propose actions. Every recommendation must
reference one supplied finding. Consequential changes, including editing values,
removing rows, resolving identifiers, and handling probable personal data, require
human approval. Treat probable personal-data findings as screening signals rather
than confirmed legal classifications.

Human clarification answers are confirmed information. Unanswered and deferred
questions remain unknown: never present them as facts. If a recommendation depends
on unresolved context, state that dependency explicitly in its assumptions field.
Do not invent research context, and do not repeat sensitive values in recommendation
text. Clarifications inform proposals only and never authorize dataset changes.
""".strip()


class AgentFinding(BaseModel):
    type: FindingType
    severity: FindingSeverity
    file: str
    affected_column: str | None
    evidence: dict[str, int | str | list[str]]


class ConfirmedClarification(BaseModel):
    related_finding: FindingReference
    question: str
    confirmed_information: str


class OpenClarification(BaseModel):
    related_finding: FindingReference
    question: str


class RecommendationContext(BaseModel):
    dataset_summary: DatasetSummary
    readiness: ReadinessSummary
    masked_findings: list[AgentFinding]
    confirmed_information: list[ConfirmedClarification] = Field(default_factory=list)
    unanswered_questions: list[OpenClarification] = Field(default_factory=list)
    deferred_questions: list[OpenClarification] = Field(default_factory=list)


def get_configured_model_name() -> str:
    model_name = os.getenv(DATAQUAY_AI_MODEL_ENV, "").strip()
    if not model_name:
        raise AIConfigurationError(
            f"{DATAQUAY_AI_MODEL_ENV} is not configured; set it to a "
            "PydanticAI provider-qualified model name."
        )
    return model_name


def build_recommendation_context(
    inspection: DatasetInspection,
    clarifications: DatasetClarifications | None = None,
) -> RecommendationContext:
    questions = clarifications.questions if clarifications else []
    return RecommendationContext(
        dataset_summary=inspection.summary,
        readiness=inspection.readiness,
        masked_findings=[
            _project_finding(finding) for finding in inspection.findings
        ],
        confirmed_information=[
            ConfirmedClarification(
                related_finding=question.related_finding,
                question=question.question,
                confirmed_information=question.answer or "",
            )
            for question in questions
            if question.status == ClarificationStatus.ANSWERED
        ],
        unanswered_questions=[
            OpenClarification(
                related_finding=question.related_finding,
                question=question.question,
            )
            for question in questions
            if question.status == ClarificationStatus.UNANSWERED
        ],
        deferred_questions=[
            OpenClarification(
                related_finding=question.related_finding,
                question=question.question,
            )
            for question in questions
            if question.status == ClarificationStatus.DEFERRED
        ],
    )


def build_recommendation_prompt(
    inspection: DatasetInspection,
    clarifications: DatasetClarifications | None = None,
) -> str:
    return build_recommendation_context(
        inspection,
        clarifications,
    ).model_dump_json(indent=2)


async def generate_recommendations(
    inspection: DatasetInspection,
    *,
    clarifications: DatasetClarifications | None = None,
    model: Model | str | None = None,
) -> RecommendationResponse:
    configured_model = model if model is not None else get_configured_model_name()

    try:
        agent = Agent(
            configured_model,
            output_type=RecommendationResponse,
            instructions=AGENT_INSTRUCTIONS,
        )
        result = await agent.run(
            build_recommendation_prompt(inspection, clarifications)
        )
    except UserError as exc:
        raise AIConfigurationError(f"Invalid AI model configuration: {exc}") from exc
    except AgentRunError as exc:
        raise AIServiceError(
            "The AI recommendation provider is unavailable or returned an invalid response."
        ) from exc

    return result.output


def _project_finding(finding: InspectionFinding) -> AgentFinding:
    evidence = finding.evidence
    if finding.type == FindingType.PROBABLE_PERSONAL_DATA:
        evidence = {
            key: value
            for key, value in finding.evidence.items()
            if key in PRIVACY_EVIDENCE_KEYS
        }
    elif finding.type == FindingType.DUPLICATE_IDENTIFIER_VALUES:
        evidence = _mask_evidence_values(finding.evidence, "duplicate_values")
    elif finding.type == FindingType.MISSING_REFERENCE:
        evidence = _mask_evidence_values(finding.evidence, "missing_values")

    return AgentFinding(
        type=finding.type,
        severity=finding.severity,
        file=finding.file,
        affected_column=finding.affected_column,
        evidence=evidence,
    )


def _mask_evidence_values(
    evidence: dict[str, int | str | list[str]], key: str
) -> dict[str, int | str | list[str]]:
    masked_evidence = evidence.copy()
    values = evidence.get(key)
    if isinstance(values, list):
        masked_evidence[key] = [_mask_identifier(value) for value in values]
    return masked_evidence


def _mask_identifier(value: str) -> str:
    if not value:
        return "***"
    return f"{value[0]}{'*' * max(len(value) - 1, 2)}"
