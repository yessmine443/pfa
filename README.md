# SPARKY (v2 — Angular 20)

Plateforme web d'intelligence documentaire pour le secteur photovoltaïque tunisien. Scanne, classifie et extrait automatiquement les données de factures, devis, bons de livraison, bons de commande et avoirs grâce à Mistral AI, avec persistance PostgreSQL, authentification sécurisée, export Google Sheets et notifications email orchestrées via n8n.

> **Cette version est l'upgrade v2** depuis Angular 17 → **Angular 20.3** + Material 20 (Material 3 design tokens) + Node 24 LTS. La version originale en Angular 17 reste disponible dans `C:\Sparky`.

---

## 🚀 Fonctionnalités

- **Scan multi-format** : PDF, JPG, PNG, TIFF
- **Classification automatique IA** : facture / devis / bon de livraison / bon de commande / avoir
- **Extraction structurée** : fournisseur, n° document, dates, montants HT/TVA/TTC, lignes articles
- **Score de confiance IA** affiché sur chaque document
- **Comparaison de prix** entre fournisseurs avec mise en évidence du moins cher
- **Catalogue stock** : articles + mouvements (entrées / sorties / inventaires / retours)
- **Export Excel** mis en forme et **Google Sheets** automatique (1 ligne par article extrait)
- **Notification email HTML** détaillée à chaque scan via n8n (tableau articles, totaux, bouton sheet)
- **Authentification sécurisée** (bcrypt, PostgreSQL `users`)
- **Tableau de bord** avec totaux par type, score IA, fournisseur, montant TTC
- **Déploiement Docker** : Orchestration complète via `docker-compose.yml`

---

## 🛠️ Stack technique

| Couche | Technologie |
|--------|-------------|
| Frontend | **Angular 20.3** (Signals, Material 3, RxJS 7.8) |
| Backend | FastAPI + Python 3.12 |
| Base de données | PostgreSQL 16 |
| ORM | SQLAlchemy async + asyncpg |
| IA | Mistral AI (`mistral-small-latest` + `pixtral-12b-2409`) |
| Workflow | n8n (notifications email + export Google Sheets) |
| Containerisation | Docker + Docker Compose |
| Export | openpyxl (Excel) + Google Sheets API |

---

## ⚙️ Déploiement et Installation

### Option 1 : Déploiement via Docker (Recommandé)

Le projet intègre une configuration complète pour Docker Desktop, simplifiant grandement le déploiement.

1. Installez [Docker Desktop](https://www.docker.com/products/docker-desktop/).
2. Copiez `.env.example` en `.env` à la racine et dans `backend/` et configurez vos clés d'API (Mistral).
3. Lancez la commande suivante à la racine du projet :
```bash
docker-compose up --build -d
```
Les services seront accessibles sur :
- **Frontend** : http://localhost
- **Backend (API)** : http://localhost:8000
- **Base de données** : localhost:5432
- **n8n** : http://localhost:5678

### Option 2 : Installation manuelle (Développement)

**Prérequis** : Python 3.12+, Node.js 24 LTS, PostgreSQL 16, n8n globalement installé.

1. **Base de données** : Créez une DB `sparky_db` avec un utilisateur `sparky`, et exécutez `\i database/schema.sql`.
2. **Backend** :
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```
Copiez et configurez `backend/.env`.
3. **Frontend** :
```bash
cd frontend
npm install
```
4. **n8n** : Importez `n8n/workflows/sparky_pipeline_ia_complet.json` dans votre instance n8n locale.
5. **Démarrage complet** : Double-cliquez sur `start-all.bat` à la racine.

---

## 🏗️ Architecture et Diagrammes

L'application suit une architecture 3-tiers moderne complétée par des services d'Intelligence Artificielle et d'automatisation :

```text
   ┌─────────────────────┐
   │  Frontend Angular   │ ← localStorage (cache)
   │  http://localhost   │
   └────────┬────────────┘
            │ POST /process
            ▼
   ┌─────────────────────┐
   │  FastAPI Backend    │
   │  http://localhost:8000
   └────┬───────┬───────┬┘
        │       │       │
        ▼       ▼       ▼
   ┌─────────┐ ┌────────────┐ ┌───────────────┐
   │Mistral AI│ │PostgreSQL │ │  n8n webhook  │
   │ Vision   │ │ sparky_db │ │   (5678)      │
   │ + Text   │ └────────────┘ └──┬──────┬─────┘
   └─────────┘                    │      │
                                  ▼      ▼
                         ┌──────────────┐ ┌────────────────┐
                         │ Google Sheets│ │  Email HTML    │
                         │   (export)   │ │  (Gmail SMTP)  │
                         └──────────────┘ └────────────────┘
```

Une documentation visuelle complète est également disponible dans le dossier `docs/diagrams/`.

**Principaux diagrammes PlantUML (.puml / .svg) inclus :**
- `01_use_cases.puml` : Diagramme des cas d'utilisation
- `02_sequence_scan_extraction.puml` : Séquence du processus de scan et d'extraction IA
- `03_sequence_price_comparison.puml` : Séquence de la comparaison de prix
- `04_pipeline_extraction_cascade.puml` : Détail du pipeline d'extraction en cascade
- `05_state_document_lifecycle.puml` : Cycle de vie d'un document
- `06_class_diagram.puml` : Diagramme de classes (Entités métier)
- `07_activity_diagram.puml` : Diagramme d'activité global
- `08_n8n_workflow.puml` : Modélisation du workflow n8n
- `09_architecture_3tiers.puml` : Vue d'architecture 3-tiers (Frontend, API, DB)

*(Générés via PlantUML, des exports SVG et PNG sont pré-inclus).*

---

## 📂 Structure du projet

```text
Sparky_V2/
├── backend/                      API FastAPI + services IA + ORM SQLAlchemy
├── database/                     Schémas SQL initiaux
├── docker-compose.yml            Orchestration Docker (frontend, backend, db, n8n)
├── docs/                         Diagrammes PlantUML et documentation visuelle
├── frontend/                     Application web Angular 20
├── n8n/                          Workflows d'automatisation (export sheets, emails)
├── test_data/                    Jeu de données de test (Factures HTML, etc.)
├── start-all.bat                 Script de lancement rapide (hors Docker)
├── RAPPORT_SPARKY.txt            Rapport de projet textuel
├── Soutenance_PFA.pptx           Présentation de soutenance PFA
├── SPARKY_Conclusion.pptx        Présentation de conclusion
├── Guide_Orateur_SPARKY.docx     Guide d'accompagnement de soutenance
└── README.md                     Documentation principale
```

---

## 📊 Pipeline n8n (11 étapes)

À chaque scan, le backend POST le webhook n8n. Le workflow exécute :
1. **Réception Document** (webhook entrée)
2. **Validation et Détection Type**
3. **Classification IA**
4. **Résultat Classification**
5. **Extraction Données IA**
6. **Résultat Extraction**
7. **Préparation lignes Google Sheet**
8. **Export Google Sheet**
9. **Construction Email HTML**
10. **Envoi Email** SMTP
11. **Réponse Finale**

---

## 👤 Auteur

**Mahmoud Elloumi** — Étudiant ingénieur en informatique  
mahmoud.elloumi@enis.tn  
Année universitaire : 2025-2026
