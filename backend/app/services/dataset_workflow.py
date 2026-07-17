from dataclasses import dataclass
from pathlib import Path
import re
import shutil

from app.services.dataset_workspace import resolve_dataset_workspace


@dataclass(frozen=True)
class DatasetWorkflowWorkspace:
    dataset_id: str
    dataset_name: str
    workspace_directory: Path
    source_directory: Path
    working_copy_directory: Path
    package_directory: Path
    package_download_url: str


def resolve_dataset_workflow_workspace(
    dataset_id: str,
    *,
    storage_root: str | Path | None = None,
) -> DatasetWorkflowWorkspace:
    """Resolve immutable input and generated-output paths for one upload."""
    workspace, metadata = resolve_dataset_workspace(
        dataset_id,
        storage_root=storage_root,
    )
    return DatasetWorkflowWorkspace(
        dataset_id=dataset_id,
        dataset_name=metadata.dataset_name,
        workspace_directory=workspace,
        source_directory=workspace / "original",
        working_copy_directory=workspace / "working-copy",
        package_directory=(
            workspace / "packages" / _safe_package_name(metadata.dataset_name)
        ),
        package_download_url=f"/api/package/datasets/{dataset_id}/download",
    )


def invalidate_generated_package(workflow: DatasetWorkflowWorkspace) -> None:
    """Remove stale generated output without touching originals or working data."""
    if workflow.package_directory.is_dir():
        shutil.rmtree(workflow.package_directory)
    workflow.package_directory.with_suffix(".zip").unlink(missing_ok=True)


def _safe_package_name(dataset_name: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "-", dataset_name).strip("-_")
    return normalized[:100] or "dataset"
