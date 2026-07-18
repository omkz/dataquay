from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.routes.audit import router as audit_router
from app.routes.clarifications import router as clarifications_router
from app.routes.datasets import router as datasets_router
from app.routes.inspect import router as inspect_router
from app.routes.package import router as package_router
from app.routes.remediate import router as remediate_router
from app.routes.validation import router as validation_router
from app.routes.workspaces import router as workspaces_router
from app.api_errors import ServiceUnavailableError

app = FastAPI(title="DataQuay API")
app.include_router(audit_router)
app.include_router(clarifications_router)
app.include_router(datasets_router)
app.include_router(inspect_router)
app.include_router(package_router)
app.include_router(remediate_router)
app.include_router(validation_router)
app.include_router(workspaces_router)


@app.exception_handler(ServiceUnavailableError)
def service_unavailable_exception_handler(
    _request: Request,
    exc: ServiceUnavailableError,
) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"code": exc.error_code.value, "detail": str(exc)},
    )


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
