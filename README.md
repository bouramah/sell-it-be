# KFSTORE — Backend

API FastAPI/SQLAlchemy pour KFSTORE, plateforme multi-boutique/multi-vendeur pour GROUPE SKF
SARL (Guinée). Sert le back-office web (`../web`), l'appli mobile interne (`../mobile`) et
l'appli mobile client (`../mobile-client`).

Production : https://admin.kfstore-gn.com (VPS 180.149.196.97).

## Stack

- Python 3.12, FastAPI, SQLAlchemy 2, Alembic (migrations), MySQL/MariaDB
- Auth JWT (jetons staff et client distincts, non interchangeables)
- SMS via NimbaSMS (OTP, réinitialisation de mot de passe) — mode "console" (journalise sans
  envoyer) si aucune clé n'est configurée
- IA via OpenAI (chatbot service client, reporting intelligent, recherche/recommandation) —
  fonctionnalités classiques (recherche floue, co-achat) sans dépendance LLM ; chatbot/reporting
  basculent sur un message de repli honnête si `OPENAI_API_KEY` est absente

## Démarrage

1. **Prérequis** : Python 3.12+, un serveur MySQL/MariaDB accessible (XAMPP, Homebrew, Docker...).

2. **Environnement virtuel et dépendances** :
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configuration** : copier `.env.example` en `.env` et ajuster au minimum `DATABASE_URL` et
   `JWT_SECRET`. Les clés SMS/OpenAI peuvent rester vides en dev (bascule automatique sur des
   fournisseurs de repli qui n'appellent aucun service externe).
   ```bash
   cp .env.example .env
   ```

4. **Base de données** — créer la base puis appliquer les migrations :
   ```bash
   mysql -h127.0.0.1 -uroot -e "CREATE DATABASE IF NOT EXISTS kfstore CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
   alembic upgrade head
   ```
   Pour peupler avec des données de démonstration réalistes : `python seed.py` (⚠️ actuellement
   cassé — importe un fixture `UTILISATEURS` qui n'existe plus dans `app/data/fixtures.py`, à
   corriger avant de compter dessus sur une base neuve).

5. **Lancer le serveur** :
   ```bash
   uvicorn app.main:app --reload
   # ou, pour être joignable depuis un téléphone/simulateur sur le même réseau :
   uvicorn app.main:app --reload --host 0.0.0.0
   ```
   API sur http://localhost:8000/api/v1, documentation interactive (Swagger) sur
   http://localhost:8000/docs.

## Migrations

```bash
alembic revision -m "description de la migration"   # créer une nouvelle révision
alembic upgrade head                                 # appliquer
alembic downgrade -1                                  # annuler la dernière
```

## Structure

- `app/main.py` — point d'entrée FastAPI, montage des routers et middlewares (CORS, audit).
- `app/routers/` — un module par domaine métier (stock, caisse, commandes, dettes, IA...).
  Les routes staff (`get_current_user`) et client (`get_current_client`) sont strictement
  séparées — deux types de jetons JWT non interchangeables (`app/core/security.py`).
- `app/core/` — config (pydantic-settings, lit `.env`), sécurité/JWT, autorisation (matrice de
  droits par rôle), middleware d'audit automatique par requête.
- `app/db_models/` — modèles SQLAlchemy (tables réelles).
- `app/models/` — schémas Pydantic (réponses API) et schémas d'écriture (payloads).
- `app/services/` — logique réutilisable indépendante des routers : `sms.py` (fournisseur SMS
  interchangeable), `ia_provider.py` (fournisseur LLM interchangeable), `pricing.py`,
  `notifications.py`, `audit.py`.
- `app/data/fixtures.py` — données de démonstration pour `seed.py` et les modules IA qui n'ont
  pas encore de dépendance LLM.
- `alembic/versions/` — historique des migrations, une par changement de schéma ou seed de
  données.

## Notes

- Les journaux d'audit sont automatiques (middleware `AuditTraceMiddleware`) : toute requête
  authentifiée sur le web, l'appli interne ou l'appli client est tracée, consultable dans
  Sécurité → Journal d'audit côté back-office.
- Le chatbot service client (`/api/v1/mon-assistant/message`, appli client) et le testeur staff
  (`/api/v1/ia/chatbot/tester`) partagent la même logique via `app/services/ia_provider.py` —
  changer de fournisseur LLM ne demande pas de réécriture des routers.
