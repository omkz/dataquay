from fastapi import FastAPI

from app.routes.audit import router as audit_router
from app.routes.datasets import router as datasets_router
from app.routes.inspect import router as inspect_router
from app.routes.package import router as package_router
from app.routes.remediate import router as remediate_router
from app.routes.validation import router as validation_router

app = FastAPI(title="DataQuay API")
app.include_router(audit_router)
app.include_router(datasets_router)
app.include_router(inspect_router)
app.include_router(package_router)
app.include_router(remediate_router)
app.include_router(validation_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
