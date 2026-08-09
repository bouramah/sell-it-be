from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    auth,
    caisse,
    clients,
    commandes,
    comptabilite,
    dashboard,
    depenses,
    dettes,
    ia,
    livraisons,
    parametres,
    produits,
    promotions,
    reseau,
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
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(reseau.router)
app.include_router(utilisateurs.router)
app.include_router(produits.router)
app.include_router(clients.router)
app.include_router(stock.router)
app.include_router(caisse.router)
app.include_router(commandes.router)
app.include_router(livraisons.router)
app.include_router(depenses.router)
app.include_router(dettes.router)
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
