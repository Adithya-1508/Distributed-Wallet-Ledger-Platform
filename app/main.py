from fastapi import FastAPI

app = FastAPI(title="Wallet Ledger Platform")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}