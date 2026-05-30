from fastapi import FastAPI

from app.api.routes import auth, users

app = FastAPI(title="Wallet Ledger Platform")


app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}