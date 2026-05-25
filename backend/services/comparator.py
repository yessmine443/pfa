"""
Price comparison service for devis (quotations).
Identifies the cheapest supplier for a given product reference.
"""
from decimal import Decimal
from typing import List
from models import CompareRequest, CompareResponse, ComparePrixResult
import structlog

log = structlog.get_logger()


class PriceComparator:
    async def compare(self, request: CompareRequest) -> CompareResponse:
        if not request.items:
            raise ValueError("La liste des devis est vide")

        results: List[ComparePrixResult] = []

        for item in request.items:
            quantite = item.quantite or Decimal("1")
            montant_total = item.montant_total
            if montant_total is None:
                montant_total = item.prix_unitaire * quantite

            results.append(
                ComparePrixResult(
                    devis_id=item.devis_id,
                    fournisseur_nom=item.fournisseur_nom,
                    prix_unitaire=item.prix_unitaire,
                    quantite=quantite,
                    montant_total=montant_total,
                    est_meilleur_prix=False,
                    devise="EUR",
                )
            )

        # Sort by unit price ascending
        results.sort(key=lambda r: r.prix_unitaire)
        meilleur = results[0]
        meilleur.est_meilleur_prix = True

        # Compute savings for each item vs cheapest
        for r in results:
            r.economie_vs_meilleur = r.montant_total - meilleur.montant_total

        # Max saving = most expensive - cheapest
        most_expensive = max(results, key=lambda r: r.montant_total)
        economie_max = most_expensive.montant_total - meilleur.montant_total

        log.info(
            "price_comparison_done",
            reference=request.reference_produit,
            nb_devis=len(results),
            meilleur_prix=str(meilleur.prix_unitaire),
            fournisseur=meilleur.fournisseur_nom,
        )

        return CompareResponse(
            reference_produit=request.reference_produit,
            designation=request.designation,
            resultats=results,
            meilleur_prix=meilleur,
            economie_max=economie_max,
        )
