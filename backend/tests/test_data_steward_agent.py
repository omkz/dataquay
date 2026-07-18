import asyncio
from pathlib import Path

import pytest
from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from app.agents.data_steward import (
    AIConfigurationError,
    build_recommendation_context,
    generate_recommendations,
    get_configured_model_name,
)
from app.schemas import ClarificationUpdateRequest
from app.services.clarifications import (
    get_dataset_clarifications,
    update_dataset_clarification,
)
from app.services.dataset_inspector import inspect_dataset

models.ALLOW_MODEL_REQUESTS = False

SAMPLE_DATASET_PATH = (
    Path(__file__).resolve().parents[2] / "sample-data" / "soil-study"
)


def test_recommendation_context_contains_only_safe_inspection_projection() -> None:
    inspection = inspect_dataset(SAMPLE_DATASET_PATH)

    context = build_recommendation_context(inspection)
    serialized_context = context.model_dump_json()

    assert set(context.model_dump()) == {
        "dataset_summary",
        "readiness",
        "masked_findings",
        "confirmed_information",
        "unanswered_questions",
        "deferred_questions",
    }
    assert context.dataset_summary.dataset_name == "soil-study"
    assert context.readiness.total_finding_count == 12
    assert "files" not in context.model_dump()
    assert "csv_profile" not in serialized_context
    assert "alice@example.com" not in serialized_context
    assert "bob@example.com" not in serialized_context
    assert "P002" not in serialized_context
    assert "P999" not in serialized_context
    assert "P***" in serialized_context

    privacy_findings = [
        finding
        for finding in context.masked_findings
        if finding.type.value == "probable_personal_data"
    ]
    assert len(privacy_findings) == 2
    assert all(
        set(finding.evidence)
        <= {
            "category",
            "occurrence_count",
            "detection_methods",
            "masked_evidence",
        }
        for finding in privacy_findings
    )


def test_recommendation_context_separates_confirmed_open_and_deferred_context(
    tmp_path: Path,
) -> None:
    inspection = inspect_dataset(SAMPLE_DATASET_PATH)
    dataset_id = "00000000-0000-4000-8000-000000000001"
    clarifications = get_dataset_clarifications(
        tmp_path,
        dataset_id=dataset_id,
        findings=inspection.findings,
    )
    answered_question = clarifications.questions[0]
    deferred_question = clarifications.questions[1]
    clarifications = update_dataset_clarification(
        tmp_path,
        dataset_id=dataset_id,
        findings=inspection.findings,
        question_id=answered_question.question_id,
        update=ClarificationUpdateRequest(
            decision="answer",
            answer="The missing value is expected; contact owner@example.com.",
        ),
    )
    clarifications = update_dataset_clarification(
        tmp_path,
        dataset_id=dataset_id,
        findings=inspection.findings,
        question_id=deferred_question.question_id,
        update=ClarificationUpdateRequest(decision="defer"),
    )

    context = build_recommendation_context(inspection, clarifications)
    serialized = context.model_dump_json()

    assert len(context.confirmed_information) == 1
    assert "[masked-email]" in context.confirmed_information[0].confirmed_information
    assert len(context.deferred_questions) == 1
    assert len(context.unanswered_questions) == len(clarifications.questions) - 2
    assert "owner@example.com" not in serialized


def test_data_steward_agent_returns_structured_recommendations_without_network() -> None:
    inspection = inspect_dataset(SAMPLE_DATASET_PATH)
    test_model = TestModel(
        custom_output_args={
            "recommendations": [
                {
                    "related_finding": {
                        "type": "missing_values",
                        "file": "participants.csv",
                        "affected_column": "email",
                    },
                    "short_title": "Review missing email values",
                    "rationale": "The email column contains a missing value.",
                    "proposed_action": "Confirm and document the missing-value policy.",
                    "confidence": 0.9,
                    "human_approval_required": True,
                    "assumptions": [
                        "The reason for the missing value remains unknown."
                    ],
                }
            ]
        }
    )

    response = asyncio.run(
        generate_recommendations(inspection, model=test_model)
    )

    assert len(response.recommendations) == 1
    recommendation = response.recommendations[0]
    assert recommendation.short_title == "Review missing email values"
    assert recommendation.related_finding.file == "participants.csv"
    assert recommendation.confidence == 0.9
    assert recommendation.human_approval_required is True
    assert recommendation.assumptions == [
        "The reason for the missing value remains unknown."
    ]


def test_missing_model_configuration_is_reported_clearly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATAQUAY_AI_MODEL", raising=False)

    with pytest.raises(
        AIConfigurationError,
        match="DATAQUAY_AI_MODEL is not configured",
    ):
        get_configured_model_name()
