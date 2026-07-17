from fastapi import FastAPI

from app.routes.inspect import router as inspect_router

app = FastAPI(title="DataQuay API")
app.include_router(inspect_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
