from fastapi import FastAPI

app = FastAPI(
    title="Teacher Planning Platform API",
    version="0.1.0",
    description="Version 1 pilot API for Anniston City Schools.",
)


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "tpp-api"}
