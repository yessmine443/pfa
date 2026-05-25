"""
Test de normalisation basé sur les données réelles du PDF fourni.

Deux fournisseurs ont les mêmes produits sous des noms différents :
  Fournisseur A (COLP250*4.7)  : "Collier Plastique 250*4.7"   qté 582
  Fournisseur B (COLP250*4.7)  : "Collier Plastic 250*4.7"     qté 200
  → doivent être fusionnés → quantité totale = 782

  Fournisseur A : "FIL SOUPLE 1*6 TERRE V/J"                  qté 840
  Fournisseur B : "CABLE SOUPLE 1X6 VERT/JAUNE"               qté 150  (inventé)
  → même câble → fusion

  Fournisseur A : "PANNEAU PHOTOVOLTAIQUE SOLAR SPACE BIFACIAL 590Wc"  qté 44
  Fournisseur B : "MODULE PV 590WC BIFACIAL"                           qté 10  (inventé)
  → même panneau → fusion
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from decimal import Decimal
from models import NormalizeLigneRequest, ImportDocumentRequest
from services.normalizer import ProductNormalizer

# ─── Couleurs terminal ───────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RED    = "\033[91m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):  print(f"  {GREEN}[OK]{RESET} {msg}")
def warn(msg): print(f"  {YELLOW}[??]{RESET} {msg}")
def err(msg): print(f"  {RED}[FAIL]{RESET} {msg}")
def title(msg): print(f"\n{BOLD}{CYAN}{'-'*60}\n  {msg}\n{'-'*60}{RESET}")

# ─── Données des deux fournisseurs (tirées du PDF) ───────────────────────────

FOURNISSEUR_A = "fourn-A-uuid"
FOURNISSEUR_B = "fourn-B-uuid"

LIGNES_A = [
    NormalizeLigneRequest(reference="COLP250*4.7",  designation="Collier Plastique 250*4.7",
                          quantite=Decimal("582"), unite="Piéce",
                          prix_unitaire=Decimal("3.74"), tva_taux=Decimal("19"),
                          fournisseur_id=FOURNISSEUR_A, document_id="doc-A"),
    NormalizeLigneRequest(reference="CV02",         designation="FIL SOUPLE 1*6 TERRE V/J",
                          quantite=Decimal("840"), unite="Métre",
                          prix_unitaire=Decimal("1.83465"), tva_taux=Decimal("19"),
                          fournisseur_id=FOURNISSEUR_A, document_id="doc-A"),
    NormalizeLigneRequest(reference="PPV590",       designation="PANNEAU PHOTOVOLTAIQUE SOLAR SPACE BIFACIAL 590Wc",
                          quantite=Decimal("44"), unite="pièce(s)",
                          prix_unitaire=Decimal("589.1"), tva_taux=Decimal("7"),
                          fournisseur_id=FOURNISSEUR_A, document_id="doc-A"),
    NormalizeLigneRequest(reference="DDF2P16CHINT", designation="DISJONCTEUR DIFF. CHINT 2P 16A",
                          quantite=Decimal("51"), unite="pièce(s)",
                          prix_unitaire=Decimal("32"), tva_taux=Decimal("19"),
                          marque="CHINT",
                          fournisseur_id=FOURNISSEUR_A, document_id="doc-A"),
    NormalizeLigneRequest(reference="CR406.5",      designation="CORNIERE ALUM 40X40 6.5 M",
                          quantite=Decimal("153"), unite="pièce(s)",
                          prix_unitaire=Decimal("69.5"), tva_taux=Decimal("19"),
                          fournisseur_id=FOURNISSEUR_A, document_id="doc-A"),
    NormalizeLigneRequest(reference="PV_6N",        designation="Câble PV 6mm² noir",
                          quantite=Decimal("0"), unite="Métre",
                          fournisseur_id=FOURNISSEUR_A, document_id="doc-A"),
    NormalizeLigneRequest(reference="PV_6R",        designation="Câble PV 6mm² rouge",
                          quantite=Decimal("0"), unite="Métre",
                          fournisseur_id=FOURNISSEUR_A, document_id="doc-A"),
    NormalizeLigneRequest(reference="PARDC2P",      designation="PARAFOUDRE DC 2P 600VDC",
                          quantite=Decimal("15"), unite="Piéce",
                          prix_unitaire=Decimal("34.2"), tva_taux=Decimal("7"),
                          fournisseur_id=FOURNISSEUR_A, document_id="doc-A"),
]

# Fournisseur B : mêmes produits, noms et références DIFFÉRENTS
LIGNES_B = [
    # Collier : "Plastic" au lieu de "Plastique", même dimension 250*4.7
    NormalizeLigneRequest(reference="COLP250*4.7",  designation="Collier Plastic 250*4.7",
                          quantite=Decimal("200"), unite="Piéce",
                          prix_unitaire=Decimal("3.74"), tva_taux=Decimal("19"),
                          fournisseur_id=FOURNISSEUR_B, document_id="doc-B"),
    # Câble souple : "CABLE SOUPLE 1X6 VERT/JAUNE" vs "FIL SOUPLE 1*6 TERRE V/J"
    NormalizeLigneRequest(reference="CAB-S-1x6-VJ", designation="CABLE SOUPLE 1X6 VERT/JAUNE",
                          quantite=Decimal("150"), unite="Métre",
                          prix_unitaire=Decimal("1.90"), tva_taux=Decimal("19"),
                          fournisseur_id=FOURNISSEUR_B, document_id="doc-B"),
    # Panneau : "MODULE PV 590WC BIFACIAL" vs "PANNEAU PHOTOVOLTAIQUE ... 590Wc"
    NormalizeLigneRequest(reference="MOD-PV-590",   designation="MODULE PV 590WC BIFACIAL",
                          quantite=Decimal("10"), unite="pièce(s)",
                          prix_unitaire=Decimal("595.0"), tva_taux=Decimal("7"),
                          fournisseur_id=FOURNISSEUR_B, document_id="doc-B"),
    # Disjoncteur : "DISJ DIFF 2P 16A" vs "DISJONCTEUR DIFF. CHINT 2P 16A"
    NormalizeLigneRequest(reference="DISJ-2P-16",   designation="DISJ DIFF 2P 16A",
                          quantite=Decimal("20"), unite="pièce(s)",
                          prix_unitaire=Decimal("33.0"), tva_taux=Decimal("19"),
                          fournisseur_id=FOURNISSEUR_B, document_id="doc-B"),
    # Câble PV noir — même article, référence légèrement différente
    NormalizeLigneRequest(reference="PV6-NOIR",     designation="Câble solaire PV 6mm² noir",
                          quantite=Decimal("300"), unite="Métre",
                          prix_unitaire=Decimal("1.20"), tva_taux=Decimal("19"),
                          fournisseur_id=FOURNISSEUR_B, document_id="doc-B"),
    # Câble PV rouge
    NormalizeLigneRequest(reference="PV6-ROUGE",    designation="Câble solaire PV 6mm² rouge",
                          quantite=Decimal("300"), unite="Métre",
                          prix_unitaire=Decimal("1.20"), tva_taux=Decimal("19"),
                          fournisseur_id=FOURNISSEUR_B, document_id="doc-B"),
    # Cornière — même dimensions
    NormalizeLigneRequest(reference="CORN-40-6.5",  designation="CORNIERE ALUMINIUM 40*40 6.5M",
                          quantite=Decimal("50"), unite="pièce(s)",
                          prix_unitaire=Decimal("72.0"), tva_taux=Decimal("19"),
                          fournisseur_id=FOURNISSEUR_B, document_id="doc-B"),
    # Parafoudre DC — même specs
    NormalizeLigneRequest(reference="PAR-DC-2P",    designation="PARAFOUDRE DC 2P 600V",
                          quantite=Decimal("5"), unite="Piéce",
                          prix_unitaire=Decimal("35.0"), tva_taux=Decimal("7"),
                          fournisseur_id=FOURNISSEUR_B, document_id="doc-B"),
]


def run():
    normalizer = ProductNormalizer()

    # ─── Import Fournisseur A ────────────────────────────────────────────────
    title("IMPORT — Fournisseur A")
    req_a = ImportDocumentRequest(
        document_id="doc-A",
        fournisseur_id=FOURNISSEUR_A,
        lignes=LIGNES_A,
        seuil_similarite=0.75,
    )
    res_a = normalizer.import_document(req_a)
    print(f"  Lignes      : {res_a.nb_lignes}")
    print(f"  Nouveaux    : {res_a.nb_nouveaux}  (articles créés)")
    print(f"  Matches     : {res_a.nb_matches}")
    for r in res_a.resultats:
        status = f"{GREEN}NOUVEAU{RESET}" if r.est_nouveau else f"{CYAN}MATCH{RESET}"
        print(f"    [{status}] {r.designation_originale[:45]:<45} → {r.reference_interne}")

    # ─── Import Fournisseur B ────────────────────────────────────────────────
    title("IMPORT — Fournisseur B (noms différents)")
    req_b = ImportDocumentRequest(
        document_id="doc-B",
        fournisseur_id=FOURNISSEUR_B,
        lignes=LIGNES_B,
        seuil_similarite=0.75,
    )
    res_b = normalizer.import_document(req_b)
    print(f"  Lignes      : {res_b.nb_lignes}")
    print(f"  Nouveaux    : {res_b.nb_nouveaux}  (articles créés — devrait être 0)")
    print(f"  Matches     : {res_b.nb_matches}")
    print(f"  Ambigus     : {res_b.nb_ambigus}")
    for r in res_b.resultats:
        status = f"{RED}NOUVEAU{RESET}" if r.est_nouveau else f"{GREEN}MATCH ✓{RESET}"
        score  = f"(score={r.score_confiance:.2f})" if not r.est_nouveau else ""
        print(f"    [{status}] {r.designation_originale[:45]:<45} → {r.reference_interne} {score}")

    # ─── Vérification des fusions attendues ─────────────────────────────────
    title("VÉRIFICATION DES FUSIONS")

    catalogue = normalizer.catalogue
    # Reconstruit quantités par article_id depuis les résultats
    qtés: dict[str, Decimal] = {}
    for r in res_a.resultats + res_b.resultats:
        # cherche quantite dans la liste originale
        for ligne in LIGNES_A + LIGNES_B:
            if ligne.designation == r.designation_originale:
                qtés[r.article_id] = qtés.get(r.article_id, Decimal(0)) + (ligne.quantite or Decimal(0))
                break

    # Attendus
    cases = [
        # (designation A, designation B, quantite_A, quantite_B)
        ("Collier Plastique 250*4.7",   "Collier Plastic 250*4.7",       582, 200),
        ("FIL SOUPLE 1*6 TERRE V/J",    "CABLE SOUPLE 1X6 VERT/JAUNE",   840, 150),
        ("PANNEAU PHOTOVOLTAIQUE SOLAR", "MODULE PV 590WC BIFACIAL",       44,  10),
        ("DISJONCTEUR DIFF. CHINT 2P",  "DISJ DIFF 2P 16A",               51,  20),
        ("Câble PV 6mm² noir",          "Câble solaire PV 6mm² noir",       0, 300),
        ("CORNIERE ALUM 40X40 6.5 M",   "CORNIERE ALUMINIUM 40*40 6.5M",  153,  50),
        ("PARAFOUDRE DC 2P 600VDC",     "PARAFOUDRE DC 2P 600V",           15,   5),
    ]

    all_ok = True
    for desig_a, desig_b, qty_a, qty_b in cases:
        # trouver l'article_id pour desig_a
        art_id_a = next((r.article_id for r in res_a.resultats if r.designation_originale.startswith(desig_a[:20])), None)
        art_id_b = next((r.article_id for r in res_b.resultats if r.designation_originale.startswith(desig_b[:20])), None)

        if art_id_a is None or art_id_b is None:
            err(f"Article non trouvé: {desig_a[:30]} | {desig_b[:30]}")
            all_ok = False
            continue

        if art_id_a == art_id_b:
            total = qty_a + qty_b
            ref = next((a["reference_interne"] for a in catalogue._articles.values() if a["id"] == art_id_a), "?")
            ok(f"FUSION OK  {repr(desig_a[:30]):<34} + {repr(desig_b[:25]):<28}"
               f" -> qte {qty_a}+{qty_b}={total}  [{ref}]")
        else:
            err(f"PAS FUSIONNE: {repr(desig_a[:30])} (id={art_id_a[:8]}) "
                f"!= {repr(desig_b[:25])} (id={art_id_b[:8]})")
            all_ok = False

    # ─── Résumé stock ────────────────────────────────────────────────────────
    title("STOCK FINAL — Catalogue canonique")
    print(f"  {'Référence interne':<35} {'Nom normalisé':<45} {'Qté A':>6} {'Qté B':>6} {'TOTAL':>7}")
    print(f"  {'-'*35} {'-'*45} {'-'*6} {'-'*6} {'-'*7}")

    # build totals by article across both imports
    article_qtés: dict[str, dict] = {}
    for r in res_a.resultats:
        qty = next((l.quantite for l in LIGNES_A if l.designation == r.designation_originale), Decimal(0)) or Decimal(0)
        if r.article_id not in article_qtés:
            article_qtés[r.article_id] = {"ref": r.reference_interne, "nom": r.nom_normalise, "qa": Decimal(0), "qb": Decimal(0)}
        article_qtés[r.article_id]["qa"] += qty

    for r in res_b.resultats:
        qty = next((l.quantite for l in LIGNES_B if l.designation == r.designation_originale), Decimal(0)) or Decimal(0)
        if r.article_id not in article_qtés:
            article_qtés[r.article_id] = {"ref": r.reference_interne, "nom": r.nom_normalise, "qa": Decimal(0), "qb": Decimal(0)}
        article_qtés[r.article_id]["qb"] += qty

    for art in sorted(article_qtés.values(), key=lambda x: x["ref"]):
        total = art["qa"] + art["qb"]
        total_str = f"{BOLD}{GREEN}{total}{RESET}" if total > 0 else str(total)
        print(f"  {art['ref']:<35} {art['nom'][:44]:<45} {art['qa']:>6} {art['qb']:>6} {total_str:>7}")

    print()
    if all_ok:
        print(f"  {BOLD}{GREEN}[SUCCES] TOUS LES TESTS PASSES{RESET}")
    else:
        print(f"  {BOLD}{RED}[ECHEC] CERTAINS TESTS ONT ECHOUE{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    run()
