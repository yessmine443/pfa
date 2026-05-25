"""
Document classification service using Google Document AI.
Falls back to keyword-based heuristics when Document AI is unavailable.
"""
import base64
import time
import re
from typing import Optional, TYPE_CHECKING
from config import settings

# Google Document AI — optional (fallback to keyword heuristics if not installed)
try:
    from google.cloud import documentai_v1 as documentai
    _DOCAI_AVAILABLE = True
except ImportError:
    documentai = None  # type: ignore
    _DOCAI_AVAILABLE = False
from models import ClassifyResponse, ClassifyPrediction, DocumentType
import structlog

log = structlog.get_logger()

# Keyword heuristics per document type (French + common)
KEYWORDS: dict[DocumentType, list[str]] = {
    DocumentType.facture: [
        "facture", "invoice", "n° facture", "numéro de facture",
        "date d'échéance", "total ttc", "montant ttc", "règlement"
    ],
    DocumentType.bon_livraison: [
        "bon de livraison", "bl n°", "livraison", "transporteur",
        "expédition", "réception", "quantité livrée", "colis"
    ],
    DocumentType.bon_commande: [
        "bon de commande", "bc n°", "commande n°", "purchase order",
        "po n°", "date de livraison prévue", "conditions de paiement"
    ],
    DocumentType.avoir: [
        "avoir", "note de crédit", "credit note", "avoir n°",
        "remboursement", "annulation facture"
    ],
    DocumentType.devis: [
        "devis", "quotation", "offre de prix", "proposition commerciale",
        "devis n°", "valable jusqu", "date de validité"
    ],
}


class DocumentClassifier:
    def __init__(self):
        self._client: Optional[object] = None

    def _get_client(self):
        if not _DOCAI_AVAILABLE or not settings.google_project_id:
            return None
        if self._client is None:
            try:
                self._client = documentai.DocumentProcessorServiceClient()
            except Exception as e:
                log.warning("document_ai_init_failed", error=str(e))
        return self._client

    async def classify(
        self,
        file_content: bytes,
        mime_type: str = "application/pdf",
        document_id: Optional[str] = None,
    ) -> ClassifyResponse:
        start = time.monotonic()

        client = self._get_client()
        if client and settings.google_processor_id:
            try:
                result = await self._classify_with_document_ai(
                    client, file_content, mime_type
                )
                result.document_id = document_id
                result.duree_ms = int((time.monotonic() - start) * 1000)
                return result
            except Exception as e:
                log.warning("document_ai_classify_failed", error=str(e))

        # Fallback 1: Mistral Vision (images) or Mistral text (PDF)
        mistral_result = await self._classify_with_mistral(file_content, mime_type)
        if mistral_result:
            mistral_result.document_id = document_id
            mistral_result.duree_ms = int((time.monotonic() - start) * 1000)
            return mistral_result

        # Fallback 2: keyword heuristics
        result = self._classify_with_keywords(file_content)
        result.document_id = document_id
        result.duree_ms = int((time.monotonic() - start) * 1000)
        return result

    async def _classify_with_document_ai(
        self,
        client: object,
        file_content: bytes,
        mime_type: str,
    ) -> ClassifyResponse:
        name = client.processor_path(
            settings.google_project_id,
            settings.google_location,
            settings.google_processor_id,
        )
        raw_document = documentai.RawDocument(content=file_content, mime_type=mime_type)
        request = documentai.ProcessRequest(name=name, raw_document=raw_document)
        response = client.process_document(request=request)
        document = response.document

        # Map Document AI classification to our types
        predictions = []
        best_type = DocumentType.facture
        best_score = 0.0

        for entity in document.entities:
            doc_type = _map_entity_type(entity.type_)
            if doc_type:
                score = float(entity.confidence)
                predictions.append(ClassifyPrediction(type_document=doc_type, score=score))
                if score > best_score:
                    best_score = score
                    best_type = doc_type

        # If Document AI returned no useful entities, fall back
        if not predictions:
            return self._classify_with_keywords(file_content)

        predictions.sort(key=lambda p: p.score, reverse=True)

        return ClassifyResponse(
            document_id=None,
            type_document=best_type,
            score_confiance=best_score,
            top_predictions=predictions[:5],
            modele_version="google-document-ai-v1",
            duree_ms=0,
        )

    async def _classify_with_mistral(
        self,
        file_content: bytes,
        mime_type: str,
    ) -> Optional[ClassifyResponse]:
        """Use Mistral AI to classify the document type."""
        if not settings.mistral_api_key:
            return None
        try:
            from mistralai import Mistral
            client = Mistral(api_key=settings.mistral_api_key)
        except ImportError:
            return None

        prompt = (
            "Quel est le type de ce document commercial ? "
            "Réponds UNIQUEMENT avec un de ces mots exacts (sans ponctuation ni explication) :\n"
            "facture\nbon_livraison\nbon_commande\navoir\ndevis"
        )

        try:
            is_image = mime_type.startswith("image/")
            if is_image:
                img_b64 = base64.b64encode(file_content).decode()
                data_url = f"data:{mime_type};base64,{img_b64}"
                response = client.chat.complete(
                    model=settings.mistral_vision_model,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": data_url}},
                            {"type": "text", "text": prompt},
                        ],
                    }],
                )
            else:
                # Extract readable text from PDF bytes for classification
                try:
                    import pdfplumber, io
                    with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                        text = "\n".join(
                            (p.extract_text() or "") for p in pdf.pages
                        )[:3000]
                except Exception:
                    text = file_content.decode("utf-8", errors="ignore")[:3000]

                if not text.strip():
                    return None

                response = client.chat.complete(
                    model=settings.mistral_model,
                    messages=[{
                        "role": "user",
                        "content": f"{prompt}\n\nDocument:\n{text}",
                    }],
                )

            raw = response.choices[0].message.content.strip().lower()
            # Extract just the type word
            for doc_type in DocumentType:
                if doc_type.value in raw:
                    best = doc_type
                    break
            else:
                return None

            log.info("mistral_classify_ok", doc_type=best.value, raw=raw)
            predictions = [ClassifyPrediction(type_document=best, score=0.92)]
            return ClassifyResponse(
                document_id=None,
                type_document=best,
                score_confiance=0.92,
                top_predictions=predictions,
                modele_version="mistral-vision-v1" if is_image else "mistral-text-v1",
                duree_ms=0,
            )

        except Exception as e:
            log.warning("mistral_classify_failed", error=str(e))
            return None

    def _classify_with_keywords(self, file_content: bytes) -> ClassifyResponse:
        # Decode bytes to text for keyword matching
        try:
            text = file_content.decode("utf-8", errors="ignore").lower()
        except Exception:
            text = ""

        scores: dict[DocumentType, float] = {}
        for doc_type, keywords in KEYWORDS.items():
            hits = sum(1 for kw in keywords if kw in text)
            scores[doc_type] = hits / len(keywords)

        sorted_types = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_type, best_score = sorted_types[0]

        # Normalize score to [0, 1] — cap at reasonable confidence
        confidence = min(best_score * 2.5, 0.95) if best_score > 0 else 0.3

        predictions = [
            ClassifyPrediction(type_document=t, score=min(s * 2.5, 0.99))
            for t, s in sorted_types
        ]

        return ClassifyResponse(
            document_id=None,
            type_document=best_type,
            score_confiance=confidence,
            top_predictions=predictions,
            modele_version="keyword-heuristic-v1",
            duree_ms=0,
        )


def _map_entity_type(entity_type: str) -> Optional[DocumentType]:
    mapping = {
        "invoice": DocumentType.facture,
        "facture": DocumentType.facture,
        "delivery_note": DocumentType.bon_livraison,
        "bon_livraison": DocumentType.bon_livraison,
        "purchase_order": DocumentType.bon_commande,
        "bon_commande": DocumentType.bon_commande,
        "credit_note": DocumentType.avoir,
        "avoir": DocumentType.avoir,
        "quotation": DocumentType.devis,
        "devis": DocumentType.devis,
    }
    return mapping.get(entity_type.lower())
