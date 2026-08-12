from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import (
    auth,
    caisse,
    clients,
    commandes,
    comptabilite,
    dashboard,
    depenses,
    dettes,
    documents,
    ia,
    livraisons,
    parametres,
    produits,
    promotions,
    reseau,
    roles,
    securite,
    stock,
    transferts,
    utilisateurs,
)

app = FastAPI(
    title="KFSTORE API",
    description="API back-office KFSTORE — GROUPE SKF SARL (prototype)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    # 5173 = back-office web ; 8081 = app mobile en mode debug web (Expo). Le natif
    # (iOS/Android) n'est pas soumis au CORS, cette liste ne concerne que le navigateur.
    allow_origins=["http://localhost:5173", "http://localhost:8081"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOADS_DIR = Path(__file__).resolve().parents[1] / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

app.include_router(auth.router)
app.include_router(reseau.router)
app.include_router(utilisateurs.router)
app.include_router(roles.router)
app.include_router(produits.router)
app.include_router(clients.router)
app.include_router(stock.router)
app.include_router(caisse.router)
app.include_router(commandes.router)
app.include_router(livraisons.router)
app.include_router(depenses.router)
app.include_router(dettes.router)
app.include_router(documents.router)
app.include_router(transferts.router)
app.include_router(comptabilite.router)
app.include_router(promotions.router)
app.include_router(ia.router)
app.include_router(securite.router)
app.include_router(parametres.router)
app.include_router(dashboard.router)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
