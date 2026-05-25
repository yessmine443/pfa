# SPARKY — Intégration n8n
## Guide complet de l'architecture et des outils IA

---

## 1. Outils IA utilisés (réellement actifs)

### Backend — Moteurs d'intelligence artificielle

| Outil | Version | Rôle | Quand utilisé |
|-------|---------|------|---------------|
| **Mistral AI — pixtral-12b-2409** | mistralai 1.5.0 | Classification + Extraction images | Fichiers JPEG, PNG, TIFF |
| **Mistral AI — mistral-small-latest** | mistralai 1.5.0 | Classification + Extraction texte | Fichiers PDF |
| **Google Document AI** | google-cloud-documentai 2.29.0 | Classification prioritaire | Si clé Google configurée |
| **pdfplumber** | — | Extraction texte PDF | Fallback si Mistral échoue |
| **Regex fallback** | — | Extraction basique | Dernier recours |

### Chaîne de traitement (pipeline réel)

```
Document recu
    │
    ├─ Étape 1 : Google Document AI     ← si GOOGLE_PROJECT_ID configuré
    │            (classification)
    │
    ├─ Étape 2 : Mistral AI             ← ACTIF (clé configurée)
    │   ├─ Image  → pixtral-12b-2409   (vision multimodale)
    │   └─ PDF    → mistral-small       (analyse texte pdfplumber)
    │
    └─ Étape 3 : pdfplumber + regex     ← fallback automatique
```

---

## 2. Applications et frameworks utilisés

### Backend (Python — FastAPI)

| Composant | Technologie | Version |
|-----------|-------------|---------|
| API REST | FastAPI | 0.111.0 |
| Serveur ASGI | Uvicorn | 0.30.0 |
| Validation données | Pydantic | 2.7.1 |
| HTTP client | httpx | 0.27.0 |
| Logging structuré | structlog | 24.2.0 |
| IA vision/texte | mistralai | 1.5.0 |
////OCR cloud | Google Document AI | 2.29.0 |
| Extraction PDF | pdfplumber | — |
| Traitement images | Pillow | 10.3.0 |

### Frontend (Angular 17)

| Composant | Technologie |
|-----------|-------------|
| Framework | Angular 17 + Signals |
| UI Components | Angular Material |
| State management | Signals (computed, signal) |
| Persistance | localStorage |
| Animations | CSS @keyframes SCSS |

### Base de données

| Environnement | Technologie | Usage |
|---------------|-------------|-------|
| Dev local | LocalStorage (Angular) | Documents scannés (frontend) |
| Dev local | SQLite (articles_db) | Articles et stock (backend) |
| n8n | SQLite | Workflows, executions, credentials |
| Production (prévu) | PostgreSQL | Toutes les données (schema.sql prêt) |

### Automatisation — n8n

| Composant | Role |
|-----------|------|
| n8n (latest) | Orchestration workflows |
| Webhook node | Reception notifications backend |
| Code node (JS) | Transformation et formatage données |
| Email Send node | Envoi notifications SMTP |
| HTTP Request node | Appels API SPARKY |

---

## 3. Architecture complète

```
┌─────────────────────────────────────────────────────────┐
│                    SPARKY ARCHITECTURE                   │
│                                                         │
│  [Angular 17]  ──POST /process──►  [FastAPI :8000]     │
│  localhost:4200                        │                │
│                              ┌─────────┴──────────┐    │
│                              │   Pipeline IA       │    │
│                              │ 1. Google DocAI     │    │
│                              │ 2. Mistral AI       │    │
│                              │    pixtral-12b      │    │
│                              │    mistral-small    │    │
│                              │ 3. pdfplumber       │    │
│                              └─────────┬──────────┘    │
│                                        │                │
│                         POST /webhook/sparky/notify     │
│                                        ▼                │
│                              [n8n :5678]                │
│                         sparky_pipeline_ia_complet      │
│                              │                          │
│                              │ 9 noeuds verts           │
│                              │ → Email HTML complet     │
│                              └──────────────────────────│
└─────────────────────────────────────────────────────────┘
```

---

## 4. Workflow actif — sparky_pipeline_ia_complet

**Déclencheur :** `POST http://localhost:5678/webhook/sparky/notify`

**Appelé par :** Backend FastAPI automatiquement après chaque scan

**9 nœuds du workflow :**

| # | Noeud | Type n8n | Fonction |
|---|-------|----------|----------|
| 1 | Reception Document | Webhook | Reçoit les données du backend |
| 2 | Validation et Detection Type | Code JS | Détecte PDF/Image, selectionne modèle IA |
| 3 | Classification IA (Mistral AI) | Code JS | Formate le résultat de classification |
| 4 | Resultat Classification | Code JS | Valide type + niveau de confiance |
| 5 | Extraction Donnees IA (Mistral AI) | Code JS | Compte articles, calcule totaux |
| 6 | Resultat Extraction | Code JS | Valide données extraites |
| 7 | Construire Email HTML | Code JS | Génère email HTML complet avec tableau |
| 8 | Envoyer Email (n8n) | Email Send | Envoie via SMTP |
| 9 | Reponse Finale | Respond Webhook | Retourne JSON au backend |

---

## 5. Email envoyé après chaque scan

Contenu de l'email généré automatiquement par n8n :

- Barre pipeline IA visuelle : Reception → Detection → Classification → Extraction → Notification
- Résultat classification : type document + score de confiance + niveau (Elevé/Moyen/Faible)
- Informations extraites : fournisseur, numéro, date, montant HT/TVA/TTC
- Tableau complet des articles : désignation, référence, quantité, prix unitaire, remise, TVA, TTC
- Moteur IA utilisé : Mistral Vision (pixtral-12b) ou Mistral Small selon le type de fichier

---

## 6. Démarrage du projet

```powershell
# Terminal 1 — Backend
cd c:\Sparky\backend
.\start.bat

# Terminal 2 — Frontend
cd c:\Sparky\frontend
npm start

# Terminal 3 — n8n
n8n start
```

**URLs :**
- Application  : http://localhost:4200
- API Backend  : http://localhost:8000
- n8n Dashboard: http://localhost:5678

---

## 7. Configuration requise (.env)

```env
MISTRAL_API_KEY=AlSTFcTTm2h5Lkizs3XoXkdiYnDSmZiu
MISTRAL_MODEL=mistral-small-latest
MISTRAL_VISION_MODEL=pixtral-12b-2409
N8N_WEBHOOK_URL=http://localhost:5678/webhook/sparky/notify
```

---

## 8. Credential SMTP dans n8n

| Champ | Valeur |
|-------|--------|
| Nom | SPARKY SMTP |
| Host | smtp.gmail.com |
| Port | 587 |
| SSL/TLS | STARTTLS |
| User | votre-email@gmail.com |
| Password | Mot de passe application Gmail (16 caractères) |
