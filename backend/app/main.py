from fastapi import FastAPI

from app.routes.inspect import router as inspect_router
from app.routes.remediate import router as remediate_router

app = FastAPI(title="DataQuay API")
app.include_router(inspect_router)
app.include_router(remediate_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
