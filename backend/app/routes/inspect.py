from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.agents.data_steward import AIConfigurationError, generate_recommendations
from app.schemas import (
    AuditAction,
    AuditStatus,
    CsvProfile,
    DatasetInspection,
    RecommendationResponse,
)
from app.services.audit_trail import append_audit_event
from app.services.clarifications import (
    get_dataset_clarifications,
    store_dataset_clarifications,
)
from app.services.csv_profiler import profile_csv
from app.services.dataset_inspector import inspect_dataset
from app.services.dataset_workspace import (
    DatasetNotFoundError,
    inspect_dataset_workspace,
)
from app.services.dataset_workflow import resolve_dataset_workflow_workspace
from app.services.workflow_repository import (
    PersistenceError,
    save_recommendation_batch,
    sync_clarifications,
    update_workspace_readiness,
)

router = APIRouter(prefix="/api/inspect", tags=["inspection"])

SAMPLE_DATASET_PATH = (
    Path(__file__).resolve().parents[3] / "sample-data" / "soil-study"
)
SAMPLE_CSV_PATH = SAMPLE_DATASET_PATH / "participants.csv"


@router.get("/sample", response_model=CsvProfile)
def inspect_sample() -> CsvProfile:
    return profile_csv(SAMPLE_CSV_PATH)


@router.get("/sample-dataset", response_model=DatasetInspection)
def inspect_sample_dataset() -> DatasetInspection:
    return inspect_dataset(SAMPLE_DATASET_PATH)


@router.get("/datasets/{dataset_id}", response_model=DatasetInspection)
def inspect_uploaded_dataset(dataset_id: str) -> DatasetInspection:
    try:
        workflow = resolve_dataset_workflow_workspace(dataset_id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        inspection = inspect_dataset_workspace(dataset_id)
    except Exception:
        append_audit_event(
            workflow.workspace_directory,
            dataset_id=dataset_id,
            action=AuditAction.INSPECTION,
            status=AuditStatus.FAILURE,
            summary="Dataset inspection failed before results were available.",
        )
        raise
    append_audit_event(
        workflow.workspace_directory,
        dataset_id=dataset_id,
        action=AuditAction.INSPECTION,
        status=AuditStatus.SUCCESS,
        summary=(
            f"Inspected {inspection.summary.total_file_count} files and produced "
            f"{inspection.readiness.total_finding_count} deterministic findings."
        ),
    )
    try:
        update_workspace_readiness(dataset_id, inspection.readiness)
    except PersistenceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return inspection


@router.post(
    "/sample-dataset/recommendations",
    response_model=RecommendationResponse,
)
async def recommend_sample_dataset_remediation() -> RecommendationResponse:
    inspection = inspect_dataset(SAMPLE_DATASET_PATH)
    try:
        return await generate_recommendations(inspection)
    except AIConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/datasets/{dataset_id}/recommendations",
    response_model=RecommendationResponse,
)
async def recommend_uploaded_dataset_remediation(
    dataset_id: str,
) -> RecommendationResponse:
    try:
        workflow = resolve_dataset_workflow_workspace(dataset_id)
        inspection = inspect_dataset_workspace(dataset_id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        generated_clarifications = get_dataset_clarifications(
            workflow.workspace_directory,
            dataset_id=dataset_id,
            findings=inspection.findings,
        )
        clarifications = sync_clarifications(generated_clarifications)
        store_dataset_clarifications(workflow.workspace_directory, clarifications)
        recommendations = await generate_recommendations(
            inspection,
            clarifications=clarifications,
        )
        save_recommendation_batch(dataset_id, recommendations)
    except AIConfigurationError as exc:
        append_audit_event(
            workflow.workspace_directory,
            dataset_id=dataset_id,
            action=AuditAction.RECOMMENDATION_GENERATION,
            status=AuditStatus.FAILURE,
            summary=(
                "Recommendation generation could not run because AI "
                "configuration was unavailable."
            ),
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception:
        append_audit_event(
            workflow.workspace_directory,
            dataset_id=dataset_id,
            action=AuditAction.RECOMMENDATION_GENERATION,
            status=AuditStatus.FAILURE,
            summary="Recommendation generation failed without returning proposals.",
        )
        raise
    append_audit_event(
        workflow.workspace_directory,
        dataset_id=dataset_id,
        action=AuditAction.RECOMMENDATION_GENERATION,
        status=AuditStatus.SUCCESS,
        summary=(
            f"Generated {len(recommendations.recommendations)} masked, "
            "proposal-only recommendations using the latest structured "
            "clarification state."
        ),
    )
    return recommendations
