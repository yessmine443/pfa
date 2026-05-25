"""
DB persistence layer for articles, articles_fournisseurs, fournisseurs.

All functions are async and use the SQLAlchemy AsyncSession already wired in database.py.

Typical flow:
  1. import_to_db(session, fournisseur_nom, lignes_result)
       → upserts fournisseur, articles, articles_fournisseurs
  2. get_comparaison_prix(session, categorie=None)
       → returns ComparaisonPrixResponse built from DB tables
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    ArticlePrixComparaison,
    ComparaisonPrixResponse,
    ImportDocumentResponse,
    NormalizeLigneResponse,
    PrixFournisseur,
)

import structlog
log = structlog.get_logger()


# ─────────────────────────────────────────────────────────────────────────────
# Upsert helpers
# ─────────────────────────────────────────────────────────────────────────────

async def upsert_fournisseur(session: AsyncSession, fournisseur_id: str, nom: str) -> str:
    """
    Insert fournisseur if not exists, return its UUID.
    fournisseur_id may be a plain UUID or an opaque string ('fourn-A').
    We treat it as external_ref and map it to a stable PG UUID.
    """
    # Try to find by the external id stored in metadata
    row = await session.execute(
        text("SELECT id FROM fournisseurs WHERE metadata->>'external_id' = :eid LIMIT 1"),
        {"eid": fournisseur_id},
    )
    existing = row.fetchone()
    if existing:
        return str(existing[0])

    # Also try by name (same supplier, different import)
    row = await session.execute(
        text("SELECT id FROM fournisseurs WHERE nom = :nom LIMIT 1"),
        {"nom": nom},
    )
    existing = row.fetchone()
    if existing:
        return str(existing[0])

    # Insert
    new_id = str(uuid.uuid4())
    await session.execute(
        text("""
            INSERT INTO fournisseurs (id, nom, metadata)
            VALUES (:id, :nom, jsonb_build_object('external_id', :eid))
            ON CONFLICT DO NOTHING
        """),
        {"id": new_id, "nom": nom, "eid": fournisseur_id},
    )
    await session.commit()
    log.info("db.fournisseur_created", nom=nom, id=new_id)
    return new_id


async def upsert_article(
    session: AsyncSession,
    reference_interne: str,
    nom_normalise: str,
    categorie: Optional[str],
    unite_mesure: Optional[str],
    specifications: Optional[dict],
) -> str:
    """
    Insert canonical article if not exists (keyed on reference_interne), return UUID.
    """
    import json

    row = await session.execute(
        text("SELECT id FROM articles WHERE reference_interne = :ref LIMIT 1"),
        {"ref": reference_interne},
    )
    existing = row.fetchone()
    if existing:
        return str(existing[0])

    new_id = str(uuid.uuid4())
    specs_json = json.dumps(specifications or {})
    await session.execute(
        text("""
            INSERT INTO articles
                (id, reference_interne, nom_normalise, categorie, unite_mesure, specifications)
            VALUES (:id, :ref, :nom, :cat, :unite, :specs::jsonb)
            ON CONFLICT (reference_interne) DO NOTHING
        """),
        {
            "id": new_id, "ref": reference_interne, "nom": nom_normalise,
            "cat": categorie, "unite": unite_mesure, "specs": specs_json,
        },
    )
    await session.commit()
    log.info("db.article_created", reference_interne=reference_interne)
    return new_id


async def upsert_article_fournisseur(
    session: AsyncSession,
    article_id: str,
    fournisseur_id: str,
    nom_fournisseur: str,
    reference_fournisseur: Optional[str],
    prix_achat: Optional[float],
    prix_vente: Optional[float],
    tva_taux: Optional[float],
    marque: Optional[str],
) -> None:
    """
    Insert or update the supplier alias for an article.
    Key: (article_id, fournisseur_id).
    """
    # Check if row already exists
    row = await session.execute(
        text("""
            SELECT id FROM articles_fournisseurs
            WHERE article_id = :art AND fournisseur_id = :fourn
            LIMIT 1
        """),
        {"art": article_id, "fourn": fournisseur_id},
    )
    existing = row.fetchone()

    if existing:
        # Update prices (keep latest)
        await session.execute(
            text("""
                UPDATE articles_fournisseurs
                SET nom_fournisseur = :nom,
                    reference_fournisseur = COALESCE(:ref, reference_fournisseur),
                    prix_achat = COALESCE(:pa, prix_achat),
                    prix_vente = COALESCE(:pv, prix_vente),
                    tva_taux   = COALESCE(:tva, tva_taux),
                    marque     = COALESCE(:marque, marque),
                    updated_at = NOW()
                WHERE article_id = :art AND fournisseur_id = :fourn
            """),
            {
                "nom": nom_fournisseur, "ref": reference_fournisseur,
                "pa": prix_achat, "pv": prix_vente, "tva": tva_taux,
                "marque": marque, "art": article_id, "fourn": fournisseur_id,
            },
        )
    else:
        new_id = str(uuid.uuid4())
        await session.execute(
            text("""
                INSERT INTO articles_fournisseurs
                    (id, article_id, fournisseur_id, nom_fournisseur, reference_fournisseur,
                     prix_achat, prix_vente, tva_taux, marque)
                VALUES (:id, :art, :fourn, :nom, :ref, :pa, :pv, :tva, :marque)
            """),
            {
                "id": new_id, "art": article_id, "fourn": fournisseur_id,
                "nom": nom_fournisseur, "ref": reference_fournisseur,
                "pa": prix_achat, "pv": prix_vente, "tva": tva_taux, "marque": marque,
            },
        )
    await session.commit()


async def add_mouvement_stock(
    session: AsyncSession,
    article_id: str,
    fournisseur_id: str,
    document_id: Optional[str],
    quantite: float,
    prix_unitaire: Optional[float],
    date_mouvement: Optional[str],
    type_mouvement: str = "entree",
) -> None:
    await session.execute(
        text("""
            INSERT INTO mouvements_stock
                (id, article_id, fournisseur_id, document_id, type_mouvement,
                 quantite, prix_unitaire, date_mouvement)
            VALUES (:id, :art, :fourn, :doc, :type, :qty, :pu,
                    COALESCE(:date::date, CURRENT_DATE))
        """),
        {
            "id": str(uuid.uuid4()),
            "art": article_id, "fourn": fournisseur_id, "doc": document_id,
            "type": type_mouvement, "qty": quantite, "pu": prix_unitaire,
            "date": date_mouvement,
        },
    )
    await session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Persist a full import result to DB
# ─────────────────────────────────────────────────────────────────────────────

async def persist_import(
    session: AsyncSession,
    import_request,           # ImportDocumentRequest
    import_result: ImportDocumentResponse,
    lignes_map: dict,         # designation → NormalizeLigneRequest
) -> None:
    """
    After normalizing all lines in memory, persist articles + supplier prices + movements to DB.
    lignes_map: maps designation → original NormalizeLigneRequest for price lookup.
    """
    # Upsert the fournisseur
    fourn_db_id = await upsert_fournisseur(
        session, import_request.fournisseur_id, import_request.fournisseur_nom
    )

    for res in import_result.resultats:
        if not res.article_id:
            continue

        # Upsert the canonical article
        art_db_id = await upsert_article(
            session,
            reference_interne=res.reference_interne,
            nom_normalise=res.nom_normalise,
            categorie=res.categorie,
            unite_mesure=None,
            specifications=res.specifications,
        )

        # Find the original ligne for pricing
        ligne = lignes_map.get(res.designation_originale)
        if ligne:
            # Upsert supplier alias with price
            await upsert_article_fournisseur(
                session,
                article_id=art_db_id,
                fournisseur_id=fourn_db_id,
                nom_fournisseur=res.designation_originale,
                reference_fournisseur=res.reference_fournisseur,
                prix_achat=float(ligne.prix_unitaire) if ligne.prix_unitaire else None,
                prix_vente=float(ligne.prix_vente) if ligne.prix_vente else None,
                tva_taux=float(ligne.tva_taux) if ligne.tva_taux else None,
                marque=ligne.marque,
            )

            # Record stock movement if quantity > 0
            qty = float(ligne.quantite) if ligne.quantite else 0.0
            if qty > 0:
                await add_mouvement_stock(
                    session,
                    article_id=art_db_id,
                    fournisseur_id=fourn_db_id,
                    document_id=import_request.document_id,
                    quantite=qty,
                    prix_unitaire=float(ligne.prix_unitaire) if ligne.prix_unitaire else None,
                    date_mouvement=str(import_request.date_mouvement) if import_request.date_mouvement else None,
                    type_mouvement=import_request.type_mouvement,
                )

    log.info("db.import_persisted", document_id=import_request.document_id,
             nb_lignes=import_result.nb_lignes)


# ─────────────────────────────────────────────────────────────────────────────
# Read comparison from DB
# ─────────────────────────────────────────────────────────────────────────────

async def get_comparaison_prix(
    session: AsyncSession,
    categorie: Optional[str] = None,
) -> ComparaisonPrixResponse:
    """
    Build the price comparison table from DB tables:
    articles + articles_fournisseurs + fournisseurs + mouvements_stock.
    """
    cat_filter = "AND a.categorie = :cat" if categorie else ""

    sql = f"""
        WITH stock AS (
            SELECT article_id,
                   SUM(CASE type_mouvement
                           WHEN 'sortie'     THEN -quantite
                           WHEN 'correction' THEN  quantite
                           ELSE                    quantite
                       END) AS quantite_totale
            FROM mouvements_stock
            GROUP BY article_id
        )
        SELECT
            a.id                    AS article_id,
            a.reference_interne,
            a.nom_normalise,
            a.categorie,
            a.unite_mesure,
            COALESCE(s.quantite_totale, 0) AS quantite_stock,
            f.id                    AS fournisseur_id,
            f.nom                   AS fournisseur_nom,
            af.nom_fournisseur,
            af.reference_fournisseur,
            af.prix_achat,
            af.prix_vente,
            af.tva_taux,
            af.marque
        FROM articles a
        LEFT JOIN stock s ON s.article_id = a.id
        JOIN articles_fournisseurs af ON af.article_id = a.id
        JOIN fournisseurs f ON f.id = af.fournisseur_id
        WHERE a.actif = TRUE
          AND af.prix_achat IS NOT NULL
          {cat_filter}
        ORDER BY a.categorie NULLS LAST, a.nom_normalise, f.nom
    """
    params: dict = {}
    if categorie:
        params["cat"] = categorie

    result = await session.execute(text(sql), params)
    rows = result.mappings().all()

    if not rows:
        return ComparaisonPrixResponse(nb_articles=0, fournisseurs=[], articles=[])

    # Group by article
    articles_dict: dict[str, dict] = {}
    fournisseurs_set: dict[str, str] = {}   # id → nom (ordered)

    for row in rows:
        art_id = str(row["article_id"])
        fourn_id = str(row["fournisseur_id"])
        fourn_nom = row["fournisseur_nom"]

        if fourn_id not in fournisseurs_set:
            fournisseurs_set[fourn_id] = fourn_nom

        if art_id not in articles_dict:
            articles_dict[art_id] = {
                "article_id":    art_id,
                "reference_interne": row["reference_interne"],
                "nom_normalise": row["nom_normalise"],
                "categorie":     row["categorie"],
                "unite_mesure":  row["unite_mesure"],
                "quantite_stock": Decimal(str(row["quantite_stock"])),
                "prix": [],
            }

        articles_dict[art_id]["prix"].append({
            "fournisseur_id":        fourn_id,
            "fournisseur_nom":       fourn_nom,
            "nom_fournisseur":       row["nom_fournisseur"],
            "reference_fournisseur": row["reference_fournisseur"],
            "prix_achat":            Decimal(str(row["prix_achat"])),
            "prix_vente":            Decimal(str(row["prix_vente"])) if row["prix_vente"] else None,
            "tva_taux":              Decimal(str(row["tva_taux"])) if row["tva_taux"] else None,
            "marque":                row["marque"],
        })

    # Build response
    articles_out: list[ArticlePrixComparaison] = []
    for art in articles_dict.values():
        prix_list = art["prix"]
        meilleur = min(prix_list, key=lambda p: float(p["prix_achat"]))
        pire_prix = max(float(p["prix_achat"]) for p in prix_list)
        meilleur_prix = float(meilleur["prix_achat"])
        economie_pct = round((pire_prix - meilleur_prix) / meilleur_prix * 100, 1) \
            if meilleur_prix > 0 and pire_prix != meilleur_prix else 0.0

        prix_par_fourn = [
            PrixFournisseur(
                fournisseur_id=p["fournisseur_id"],
                fournisseur_nom=p["fournisseur_nom"],
                nom_fournisseur=p["nom_fournisseur"],
                reference_fournisseur=p["reference_fournisseur"],
                prix_achat=p["prix_achat"],
                prix_vente=p.get("prix_vente"),
                tva_taux=p.get("tva_taux"),
                marque=p.get("marque"),
                est_meilleur_prix=(p["fournisseur_id"] == meilleur["fournisseur_id"]),
                surcout_pct=round((float(p["prix_achat"]) - meilleur_prix) / meilleur_prix * 100, 1)
                    if float(p["prix_achat"]) != meilleur_prix else 0.0,
            )
            for p in sorted(prix_list, key=lambda x: float(x["prix_achat"]))
        ]

        articles_out.append(ArticlePrixComparaison(
            article_id=art["article_id"],
            reference_interne=art["reference_interne"],
            nom_normalise=art["nom_normalise"],
            categorie=art["categorie"],
            unite_mesure=art["unite_mesure"],
            quantite_stock=art["quantite_stock"],
            meilleur_prix_achat=meilleur["prix_achat"],
            meilleur_fournisseur=meilleur["fournisseur_nom"],
            economie_max_pct=economie_pct,
            prix_par_fournisseur=prix_par_fourn,
        ))

    return ComparaisonPrixResponse(
        nb_articles=len(articles_out),
        fournisseurs=list(fournisseurs_set.values()),
        articles=articles_out,
    )
