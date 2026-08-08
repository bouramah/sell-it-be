from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import boutiques, dashboard, stock, utilisateurs

app = FastAPI(
    title="KFSTORE API",
    description="API back-office KFSTORE — GROUPE SKF SARL (prototype)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(boutiques.router)
app.include_router(stock.router)
app.include_router(utilisateurs.router)
app.include_router(dashboard.router)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
