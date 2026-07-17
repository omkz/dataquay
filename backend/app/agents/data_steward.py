import os

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.exceptions import UserError
from pydantic_ai.models import Model

from app.schemas import (
    DatasetInspection,
    DatasetSummary,
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
""".strip()


class AgentFinding(BaseModel):
    type: FindingType
    severity: FindingSeverity
    file: str
    affected_column: str | None
    evidence: dict[str, int | str | list[str]]


class RecommendationContext(BaseModel):
    dataset_summary: DatasetSummary
    readiness: ReadinessSummary
    masked_findings: list[AgentFinding]


class AIConfigurationError(RuntimeError):
    """Raised when the Data Steward Agent cannot be configured safely."""


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
) -> RecommendationContext:
    return RecommendationContext(
        dataset_summary=inspection.summary,
        readiness=inspection.readiness,
        masked_findings=[
            _project_finding(finding) for finding in inspection.findings
        ],
    )


def build_recommendation_prompt(inspection: DatasetInspection) -> str:
    return build_recommendation_context(inspection).model_dump_json(indent=2)


async def generate_recommendations(
    inspection: DatasetInspection,
    *,
    model: Model | str | None = None,
) -> RecommendationResponse:
    configured_model = model if model is not None else get_configured_model_name()

    try:
        agent = Agent(
            configured_model,
            output_type=RecommendationResponse,
            instructions=AGENT_INSTRUCTIONS,
        )
        result = await agent.run(build_recommendation_prompt(inspection))
    except UserError as exc:
        raise AIConfigurationError(f"Invalid AI model configuration: {exc}") from exc

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
