import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.audit_middleware import AuditTraceMiddleware

# Sans ceci, les loggers applicatifs ("kfstore.*" : sms, push, notifications) n'ont aucun
# handler sous un `uvicorn app.main:app` lancé directement (systemd, gunicorn...) — leurs logs
# disparaissent silencieusement. En local ils n'apparaissaient que parce que le wrapper de
# lancement appelait explicitement logging.basicConfig() avant d'importer uvicorn. Root laissé
# en WARNING (pas de bruit des libs tierces type weasyprint) — seul "kfstore" passe en INFO.
logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("kfstore").setLevel(logging.INFO)

from app.routers import (
    aide_enseignants,
    auth,
    caisse,
    catalogue,
    client_auth,
    clients,
    commandes,
    comptabilite,
    dashboard,
    depenses,
    dettes,
    documents,
    ecoles,
    enseignants,
    geographie,
    ia,
    livraisons,
    mes_commandes,
    mon_assistant,
    mon_credit,
    notifications,
    parametres,
    produits,
    promotions,
    reseau,
    roles,
    securite,
    stock,
    transferts,
    utilisateurs,
    validation_garant,
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
app.add_middleware(AuditTraceMiddleware)

UPLOADS_DIR = Path(__file__).resolve().parents[1] / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

app.include_router(auth.router)
app.include_router(client_auth.router)
app.include_router(catalogue.router)
app.include_router(mes_commandes.router)
app.include_router(mon_credit.router)
app.include_router(mon_assistant.router)
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
app.include_router(geographie.router)
app.include_router(transferts.router)
app.include_router(comptabilite.router)
app.include_router(promotions.router)
app.include_router(ia.router)
app.include_router(securite.router)
app.include_router(parametres.router)
app.include_router(dashboard.router)
app.include_router(notifications.router)
app.include_router(ecoles.router)
app.include_router(enseignants.router)
app.include_router(validation_garant.router)
app.include_router(aide_enseignants.router)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
