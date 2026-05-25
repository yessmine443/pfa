"""
Data extraction service.
Priority: Mistral AI > pdfplumber (PDF) > pytesseract (images) > easyocr > regex fallback.
"""
import io
import time
import re
import json
import base64
from decimal import Decimal
from datetime import date
from typing import Optional, List

# pdfplumber — PDF text extraction
try:
    import pdfplumber
    _PDFPLUMBER_AVAILABLE = True
except ImportError:
    _PDFPLUMBER_AVAILABLE = False

# pytesseract — OCR for images (requires Tesseract binary)
try:
    import pytesseract
    from PIL import Image
    # Windows default install path
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    _TESSERACT_AVAILABLE = True
except ImportError:
    _TESSERACT_AVAILABLE = False

# easyocr — fallback OCR (no binary required)
try:
    import easyocr
    import numpy as np
    if not _TESSERACT_AVAILABLE:
        from PIL import Image
    _EASYOCR_AVAILABLE = True
except ImportError:
    _EASYOCR_AVAILABLE = False

from config import settings
from models import (
    DocumentType, ExtractResponse,
    ExtractedFacture, ExtractedBonLivraison, ExtractedBonCommande,
    ExtractedAvoir, ExtractedDevis, LigneDocument,
)
import structlog

log = structlog.get_logger()


class DocumentExtractor:
    def __init__(self):
        pass

    async def extract(
        self,
        file_content: bytes,
        mime_type: str,
        document_id: str,
        type_document: DocumentType,
    ) -> ExtractResponse:
        start = time.monotonic()
        donnees: dict = {}

        # 1. Mistral AI (OCR + structured extraction)
        donnees = await self._extract_with_mistral(file_content, mime_type, type_document)

        # 2. pdfplumber + regex fallback
        if not donnees or _is_empty(donnees):
            text = _extract_text(file_content, mime_type)
            if text:
                donnees = _extract_with_regex(text, type_document)

        # 3. Ensure structure is always returned
        if not donnees:
            donnees = _empty_structure(type_document)

        return ExtractResponse(
            document_id=document_id,
            type_document=type_document,
            donnees=donnees,
            duree_ms=int((time.monotonic() - start) * 1000),
        )

    async def _extract_with_mistral(
        self,
        file_content: bytes,
        mime_type: str,
        type_document: DocumentType,
    ) -> dict:
        """Use Mistral AI to extract structured data from a document."""
        if not settings.mistral_api_key:
            return {}

        try:
            from mistralai import Mistral
            client = Mistral(api_key=settings.mistral_api_key)
        except ImportError:
            log.warning("mistral_not_installed")
            return {}

        system_prompt = (
            "Tu es un expert en extraction de données de documents commerciaux "
            "(factures, devis, bons de commande, bons de livraison, avoirs).\n"
            "Extrais les informations structurées et retourne UNIQUEMENT un JSON valide "
            "sans texte ni balises markdown.\n\n"
            "Format attendu:\n"
            "{\n"
            '  "fournisseur_nom": "...",\n'
            '  "numero_document": "...",\n'
            '  "date_document": "DD/MM/YYYY ou null",\n'
            '  "montant_ht": 0.00,\n'
            '  "montant_tva": 0.00,\n'
            '  "montant_ttc": 0.00,\n'
            '  "lignes": [\n'
            '    {\n'
            '      "reference": "... ou null",\n'
            '      "designation": "...",\n'
            '      "quantite": 1.0,\n'
            '      "unite": "... ou null",\n'
            '      "prix_unitaire": 0.00,\n'
            '      "remise_pct": 0.00,\n'
            '      "tva_taux": 19.0,\n'
            '      "montant_ht": 0.00,\n'
            '      "montant_ttc": 0.00\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "RÈGLES STRICTES:\n"
            "- lignes = uniquement les vrais articles/produits/services commandés\n"
            "- NE PAS inclure: lignes de total, sous-total, TVA, timbre fiscal, remise globale\n"
            "- tva_taux = le TAUX en % (ex: 19, 7, 13) — jamais le montant TVA\n"
            "- Tous les montants sont en dinars tunisiens (TND)\n"
            "- Retourner null pour les champs absents du document"
        )

        is_image = mime_type.startswith("image/")

        try:
            if is_image:
                img_b64 = base64.b64encode(file_content).decode()
                data_url = f"data:{mime_type};base64,{img_b64}"
                response = client.chat.complete(
                    model=settings.mistral_vision_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": [
                                {"type": "image_url", "image_url": {"url": data_url}},
                                {"type": "text", "text": f"Extrais les données de ce {type_document.value}."},
                            ],
                        },
                    ],
                )
            else:
                text = _extract_text(file_content, mime_type)
                if not text or len(text) < 30:
                    return {}
                response = client.chat.complete(
                    model=settings.mistral_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": (
                                f"Extrais les données structurées de ce {type_document.value}:\n\n"
                                + text[:8000]
                            ),
                        },
                    ],
                )

            raw = response.choices[0].message.content.strip()
            # Strip markdown code fences if present
            fence = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
            if fence:
                raw = fence.group(1)

            data = json.loads(raw)
            result = _map_mistral_result(data, type_document)
            log.info(
                "mistral_extract_ok",
                doc_type=type_document.value,
                lignes=len(data.get("lignes", [])),
            )
            return result

        except json.JSONDecodeError as e:
            log.warning("mistral_json_parse_failed", error=str(e))
            return {}
        except Exception as e:
            log.warning("mistral_extract_failed", error=str(e))
            return {}

# ============================================================
# TEXT EXTRACTION
# ============================================================

def _extract_text(file_content: bytes, mime_type: str) -> str:
    """Extract raw text from PDF or image."""
    text = ""

    if "pdf" in mime_type and _PDFPLUMBER_AVAILABLE:
        try:
            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                parts: List[str] = []
                for page in pdf.pages:
                    # Plain text first (headers, totals, metadata)
                    plain = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
                    if plain:
                        parts.append(plain)
                    # Table extraction — most reliable for line items
                    for table in page.extract_tables() or []:
                        for row in table:
                            if not row:
                                continue
                            # Clean embedded newlines from multi-line header cells
                            cells = [re.sub(r"\s+", " ", str(c)).strip() if c else "" for c in row]
                            # Skip fully empty rows
                            if not any(cells):
                                continue
                            parts.append("\t".join(cells))
                text = "\n".join(parts)
                log.info("pdf_text_extracted", chars=len(text), pages=len(pdf.pages))
        except Exception as e:
            log.warning("pdfplumber_failed", error=str(e))

    # Image OCR — Tesseract (priority) then easyocr (fallback)
    if not text and mime_type.startswith("image/"):

        # 1. Tesseract
        if _TESSERACT_AVAILABLE:
            try:
                image = Image.open(io.BytesIO(file_content))
                log.info("ocr_starting_tesseract")
                text = pytesseract.image_to_string(image, lang="fra+eng")
                log.info("ocr_tesseract_done", chars=len(text))
            except Exception as e:
                log.warning("tesseract_failed", error=str(e))
                text = ""

        # 2. easyocr fallback
        if not text and _EASYOCR_AVAILABLE:
            try:
                image = Image.open(io.BytesIO(file_content))
                img_np = np.array(image)
                log.info("ocr_starting_easyocr")
                reader = easyocr.Reader(['fr', 'en'], gpu=False, verbose=False)
                result = reader.readtext(img_np, detail=0)
                text = "\n".join(result)
                log.info("ocr_easyocr_done", chars=len(text))
            except Exception as e:
                log.warning("easyocr_failed", error=str(e))

    return text


def _is_empty(donnees: dict) -> bool:
    """Check if extraction result has no meaningful data."""
    skip = {"devise", "lignes"}
    return all(
        v is None or v == [] or v == "" or k in skip
        for k, v in donnees.items()
    )


# ============================================================
# REGEX EXTRACTION from raw text
# ============================================================

def _extract_with_regex(text: str, doc_type: DocumentType) -> dict:
    t = text  # keep original case for some patterns

    def find(pattern: str, flags: int = re.IGNORECASE | re.MULTILINE) -> Optional[str]:
        m = re.search(pattern, t, flags)
        return m.group(1).strip() if m else None

    # ---- Common fields ----
    montant_ttc  = find(r"(?:total\s*(?:ttc|tva\s*compris[e]?|general)|montant\s*ttc)[^\d]*(\d[\d\s.,]+)")
    montant_ht   = find(r"(?:total\s*h\.?t\.?|montant\s*h\.?t\.?|sous[\s-]total)[^\d]*(\d[\d\s.,]+)")
    fournisseur  = find(r"(?:(?:société|raison\s+sociale|entreprise|fournisseur)\s*[:\-]?\s*)([A-ZÀ-Ü][^\n\r]{2,60})")
    date_str     = find(r"(?:date\s*(?:du\s*devis|facture|livraison|commande)?|le)\s*[:\-]?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})")

    # ---- Line items extraction ----
    lignes = _extract_lignes(text)

    base: dict = {
        "fournisseur_nom": fournisseur,
        "montant_ht": _clean_decimal(montant_ht),
        "montant_ttc": _clean_decimal(montant_ttc),
        "devise": "TND",
        "lignes": [l.model_dump() for l in lignes],
    }

    if doc_type == DocumentType.facture:
        base["numero_facture"] = find(r"(?:facture\s*n[°o]?\.?\s*[:\-]?\s*)([A-Z0-9][\w\-/]{1,30})")
        base["date_facture"] = date_str
        base["date_echeance"] = find(r"(?:échéance|due\s*date|payer\s*avant)\s*[:\-]?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})")

    elif doc_type == DocumentType.devis:
        base["numero_devis"] = find(r"(?:devis\s*n[°o]?\.?\s*[:\-]?\s*)([A-Z0-9][\w\-/]{1,30})")
        base["date_devis"] = date_str
        base["date_validite"] = find(r"(?:valable?\s*(?:jusqu[''`]au?|le)?|validité)\s*[:\-]?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})")

    elif doc_type == DocumentType.bon_livraison:
        base["numero_bl"] = find(r"(?:(?:bon\s*de\s*)?livraison\s*n[°o]?\.?\s*[:\-]?\s*|bl\s*n[°o]?\s*[:\-]?\s*)([A-Z0-9][\w\-/]{1,30})")
        base["date_livraison"] = date_str
        base["transporteur"] = find(r"(?:transporteur|carrier|livreur)\s*[:\-]?\s*([^\n\r]{3,50})")

    elif doc_type == DocumentType.bon_commande:
        base["numero_bc"] = find(r"(?:(?:bon\s*de\s*)?commande\s*n[°o]?\.?\s*[:\-]?\s*|bc\s*n[°o]?\s*[:\-]?\s*|po\s*#?\s*)([A-Z0-9][\w\-/]{1,30})")
        base["date_commande"] = date_str

    elif doc_type == DocumentType.avoir:
        base["numero_avoir"] = find(r"(?:avoir\s*n[°o]?\.?\s*[:\-]?\s*)([A-Z0-9][\w\-/]{1,30})")
        base["date_avoir"] = date_str
        base["motif"] = find(r"(?:motif|raison|objet)\s*[:\-]?\s*([^\n\r]{3,100})")

    return base


def _extract_lignes(text: str) -> List[LigneDocument]:
    """
    Extract line items using header-aware column detection.
    Supports all common Tunisian document formats (STAROIL, SEMO, GPC, RENER, COPAL, etc.)
    """
    lignes: List[LigneDocument] = []

    # ── keyword sets for header column detection ──
    _REF_KW  = {"réf", "ref", "référence", "reference", "code", "art.", "art"}
    _DESC_KW = {"désignation", "designation", "description", "libellé", "libelle",
                "produit", "article", "nom", "déscrip", "libelle"}
    _QTY_KW  = {"qté", "qte", "quantité", "quantite", "qty", "qt", "nb", "q"}
    _UNIT_KW = {"unité", "unite", "u."}
    _PU_KW   = {"p.u", "p.unit", "prix_u", "prix u", "pu ht", "p.u.ht",
                "htva", "prix unitaire", "unit.ht", "prix u. ht", "p.unit.ht"}
    _REM_KW  = {"remise", "rem", "r.%", "rabais", "r."}
    _TVA_KW  = {"tva", "tax", "taux tva", "tx tva"}  # "taxes" removed — means remise in GPC format
    _HT_KW   = {"montant ht", "total ht", "net ht", "net h.t", "p.tot.ht",
                "montant hors", "ht", "total htva", "montant htva", "net h.t.",
                "montant"}
    _TTC_KW  = {"ttc", "net ttc", "montant ttc", "total ttc", "net tva compris",
                "prix ttc", "net t.t.c"}
    _SKIP_WORDS = {
        "total", "sous-total", "timbre", "net à payer", "arrêté",
        "remise globale", "base tva", "montant tva", "taux tva", "total ht",
        "total tva", "total ttc", "net ht", "validité", "arrêté",
        "signature", "cachet", "credit", "timbre fiscal",
    }

    def _is_num(s: str) -> bool:
        return bool(re.match(r"^\d[\d\s.,]*$", s.strip()))

    def _clean_cell(s: str) -> str:
        """Remove newlines/extra spaces and fix doubled-character PDF artifacts."""
        s = re.sub(r"\s+", " ", s.replace("\n", " ")).strip()
        # Fix doubled chars: TToottaall → Total  (PDF rendering artefact)
        words = s.split()
        fixed = []
        for w in words:
            if len(w) >= 4 and len(w) % 2 == 0:
                half = len(w) // 2
                if all(w[i * 2] == w[i * 2 + 1] for i in range(half)):
                    w = w[::2]
            fixed.append(w)
        return " ".join(fixed)

    def _find_header(rows: List[List[str]]) -> Optional[int]:
        """Return index of the row that best matches a table header."""
        _HEADER_KW = [
            "désignation", "designation", "description", "libellé", "libelle", "produit",
            "qté", "quantité", "quantite", "prix unitaire", "prix", "montant",
            "référence", "ref", "p.u", "p.unit", "ht", "remise", "tva",
            "taxes", "total", "unité",
        ]
        best_score, best_idx = 1, None
        for i, row in enumerate(rows[:30]):
            cleaned = [_clean_cell(c).lower() for c in row]
            txt = " ".join(cleaned)
            # Score: each keyword match + bonus for multi-column row
            score = sum(1 for kw in _HEADER_KW if kw in txt)
            score += min(len(row), 5) * 0.1  # slight bonus for wider rows
            if score > best_score:
                best_score, best_idx = score, i
        return best_idx

    def _build_map(header: List[str]) -> dict:
        """Map semantic field names to column indices."""
        m: dict = {}
        for i, raw in enumerate(header):
            c = _clean_cell(raw).lower()
            if not c:
                continue
            if "ref" not in m and any(k in c for k in _REF_KW):
                m["ref"] = i
            elif "desc" not in m and any(k in c for k in _DESC_KW):
                m["desc"] = i
            elif "qty" not in m and any(k in c for k in _QTY_KW):
                m["qty"] = i
            # "pu" before "unit" — prevents "prix_u h.t" from matching "u." in _UNIT_KW
            elif "pu" not in m and any(k in c for k in _PU_KW):
                m["pu"] = i
            elif "unit" not in m and any(k in c for k in _UNIT_KW):
                m["unit"] = i
            elif "rem" not in m and any(k in c for k in _REM_KW):
                m["rem"] = i
            elif "tva" not in m and any(k in c for k in _TVA_KW) and "htva" not in c:
                m["tva"] = i
            elif "ttc" not in m and any(k in c for k in _TTC_KW):
                m["ttc"] = i
            # Exclude "Montant TVA" / "Montant TTC" from mapping to "ht"
            elif "ht" not in m and any(k in c for k in _HT_KW) and "tva" not in c and "ttc" not in c:
                m["ht"] = i
        return m

    def _get(row: List[str], col_map: dict, key: str) -> str:
        idx = col_map.get(key)
        if idx is None or idx >= len(row):
            return ""
        return _clean_cell(row[idx])

    def _parse_mapped(row: List[str], col_map: dict) -> Optional[LigneDocument]:
        desc  = _get(row, col_map, "desc")
        ref   = _get(row, col_map, "ref")
        qty_s = _get(row, col_map, "qty")
        pu_s  = _get(row, col_map, "pu")
        ht_s  = _get(row, col_map, "ht")
        rem_s = _get(row, col_map, "rem")
        tva_s = _get(row, col_map, "tva")
        ttc_s = _get(row, col_map, "ttc")
        uni_s = _get(row, col_map, "unit")

        designation = desc or ref
        if not designation or len(designation) < 2:
            return None

        # Skip purely numeric designations (TVA base rows like "4 276,446")
        if re.match(r"^[\d\s.,]+%?$", designation.strip()):
            return None

        low = designation.lower()
        if any(w in low for w in _SKIP_WORDS):
            return None

        # Stop at secondary table headers
        row_text = " ".join(row).lower()
        if sum(1 for kw in ["base tva", "montant tva", "taux tva", "total ht", "total tva"] if kw in row_text) >= 1:
            return None

        # ── Fix column misalignment ──
        # If mapped ht_s is non-numeric (e.g. "TVA 7%" due to header/data col count mismatch),
        # fall back to the last purely numeric cell in the row.
        def _is_numeric_cell(s: str) -> bool:
            return bool(s) and bool(re.match(r"^[\d\s.,]+$", s.strip()))

        if ht_s and not _is_numeric_cell(ht_s):
            ht_s = ""
            for cv in reversed([_clean_cell(c) for c in row]):
                if _is_numeric_cell(cv):
                    ht_s = cv
                    break

        # If mapped pu_s is non-numeric, try the column just before the last numeric
        if pu_s and not _is_numeric_cell(pu_s):
            numeric_cols = [_clean_cell(c) for c in row if _is_numeric_cell(_clean_cell(c))]
            pu_s = numeric_cols[-2] if len(numeric_cols) >= 2 else ""

        # Extract TVA rate from "TVA X%" pattern anywhere in the row
        if not tva_s or not _is_numeric_cell(re.sub(r"[%TVAtva\s]", "", tva_s)):
            for cv in [_clean_cell(c) for c in row]:
                m_tva = re.search(r"(?:TVA|tva)\s*(\d+(?:[.,]\d+)?)\s*%", cv)
                if m_tva:
                    tva_s = m_tva.group(1)
                    break

        # ref valid only if not a plain ordinal (1, 2, 3...)
        reference = ref if ref and ref != desc and not re.match(r"^\d{1,3}$", ref.strip()) else None

        qty_val = _clean_decimal(qty_s) if qty_s else None
        pu_val  = _clean_decimal(pu_s)  if pu_s  else None
        ht_val  = _clean_decimal(ht_s)  if ht_s  else None
        ttc_val = _clean_decimal(ttc_s) if ttc_s else None

        # Reject header-fragment rows that have no numeric data at all
        if qty_val is None and pu_val is None and ht_val is None and ttc_val is None:
            return None

        return LigneDocument(
            reference=reference or None,
            designation=designation,
            quantite=qty_val,
            unite=uni_s or None,
            prix_unitaire=pu_val,
            montant_ht=ht_val,
            remise_pct=_clean_decimal(re.sub(r"[%\s]", "", rem_s)) if rem_s else None,
            tva_taux=_clean_decimal(tva_s) if tva_s else None,
            montant_ttc=ttc_val,
        )

    # ── 1. Tab-separated (pdfplumber extract_tables) ──
    tab_lines = [ln for ln in text.splitlines() if "\t" in ln]
    if tab_lines:
        rows = [[c.strip() for c in ln.split("\t")] for ln in tab_lines]
        header_idx = _find_header(rows)

        if header_idx is not None:
            col_map = _build_map(rows[header_idx])
            # If we found desc or ref column, use mapped parsing
            if "desc" in col_map or "ref" in col_map:
                for row in rows[header_idx + 1:]:
                    if not any(row):
                        continue
                    ligne = _parse_mapped(row, col_map)
                    if ligne:
                        lignes.append(ligne)

        # Fallback positional if header-based gave nothing
        if not lignes:
            for row in rows:
                if len(row) < 3:
                    continue
                row_text = " ".join(row).lower()
                # Skip header/footer rows
                if sum(1 for h in ["désignation","designation","quantité","prix","montant","référence"] if h in row_text) >= 2:
                    continue
                if any(w in row_text for w in _SKIP_WORDS):
                    continue

                # Try positional: ref? | desc | qty | pu | ht
                first = _clean_cell(row[0])
                # Skip TVA rate rows like "7.00%" or "19.00%"
                if re.match(r"^\d+(?:[.,]\d+)?\s*%$", first.strip()):
                    continue
                first_is_ref = (
                    2 <= len(first) <= 30
                    and not _is_num(first)
                    and not first.lower().startswith(("total","sous","remise","tva","timbre"))
                )
                if first_is_ref and len(row) >= 4:
                    ref, desc = first, _clean_cell(row[1])
                    qty = _clean_decimal(row[2]) if _is_num(row[2]) else None
                    pu  = _clean_decimal(row[3]) if _is_num(row[3]) else None
                    ht  = _clean_decimal(row[4]) if len(row) > 4 and _is_num(row[4]) else None
                else:
                    ref, desc = None, _clean_cell(row[0])
                    # Skip TVA rate designations
                    if re.match(r"^\d+(?:[.,]\d+)?\s*%$", desc.strip()):
                        continue
                    qty = _clean_decimal(row[1]) if _is_num(row[1]) else None
                    pu  = _clean_decimal(row[2]) if _is_num(row[2]) else None
                    ht  = _clean_decimal(row[3]) if len(row) > 3 and _is_num(row[3]) else None

                if not desc or len(desc) < 2:
                    continue
                if any(w in desc.lower() for w in _SKIP_WORDS):
                    continue
                if pu is None and ht is None and qty is None:
                    continue

                lignes.append(LigneDocument(
                    reference=ref,
                    designation=desc,
                    quantite=qty,
                    prix_unitaire=pu,
                    montant_ht=ht,
                ))

    # ── 2. Specialized pattern: Ord | Libellé | Qté | P.Unit.HT | R.% | Net HT | TVA% | Net TTC ──
    # Handles RENER, STAROIL and similar 8-column formats
    if not lignes:
        ord_pattern = re.compile(
            r"^(\d+)\s+(.+?)\s+(\d+(?:[.,]\d+)?)\s+([\d.,]+)\s+(\d+(?:[.,]\d+)?)\s+([\d.,]+)\s+(\d+(?:[.,]\d+)?)\s+([\d.,]+)$",
            re.MULTILINE,
        )
        for m in ord_pattern.finditer(text):
            des = m.group(2).strip()
            if len(des) < 3:
                continue
            if any(w in des.lower() for w in _SKIP_WORDS):
                continue
            lignes.append(LigneDocument(
                designation=des,
                quantite=_clean_decimal(m.group(3)),
                prix_unitaire=_clean_decimal(m.group(4)),
                remise_pct=_clean_decimal(m.group(5)),
                montant_ht=_clean_decimal(m.group(6)),
                tva_taux=_clean_decimal(m.group(7)),
                montant_ttc=_clean_decimal(m.group(8)),
            ))

    # ── 3. Regex fallback (plain text / OCR output) ──
    if not lignes:
        line_pattern = re.compile(
            r"^(.{5,70}?)\s+(\d+(?:[.,]\d+)?)\s+(\d[\d\s.,]+)\s+(\d[\d\s.,]+)$",
            re.MULTILINE,
        )
        for m in line_pattern.finditer(text):
            des = m.group(1).strip()
            if any(h in des.lower() for h in ["désignation","description","quantit","prix","montant","référence"]):
                continue
            if len(des) < 3:
                continue
            lignes.append(LigneDocument(
                designation=des,
                quantite=_clean_decimal(m.group(2)),
                prix_unitaire=_clean_decimal(m.group(3)),
                montant_ht=_clean_decimal(m.group(4)),
            ))

    # ── 4. Last resort: lines with one price ──
    if not lignes:
        for m in re.finditer(r"^(.{5,80}?)\s+((?:\d+[\s.,]\d+|\d+)[DT$€]?)$", text, re.MULTILINE):
            des = m.group(1).strip()
            if any(w in des.lower() for w in ["total","tva","ttc","remise","timbre"]):
                continue
            price = _clean_decimal(re.sub(r"[DT$€\s]", "", m.group(2)))
            if price and price > Decimal("0"):
                lignes.append(LigneDocument(designation=des, montant_ht=price))

    return lignes[:50]


def _map_mistral_result(data: dict, doc_type: DocumentType) -> dict:
    """Convert Mistral AI JSON output to our internal format."""

    def _num(v) -> Optional[Decimal]:
        if v is None:
            return None
        return _clean_decimal(str(v))

    lignes = []
    for item in data.get("lignes", []):
        des = item.get("designation") or ""
        if not des or len(des) < 2:
            continue
        lignes.append(LigneDocument(
            reference=item.get("reference") or None,
            designation=des,
            quantite=_num(item.get("quantite")),
            unite=item.get("unite") or None,
            prix_unitaire=_num(item.get("prix_unitaire")),
            remise_pct=_num(item.get("remise_pct")),
            tva_taux=_num(item.get("tva_taux")),
            montant_ht=_num(item.get("montant_ht")),
            montant_ttc=_num(item.get("montant_ttc")),
        ))

    base: dict = {
        "fournisseur_nom": data.get("fournisseur_nom"),
        "montant_ht": _num(data.get("montant_ht")),
        "montant_tva": _num(data.get("montant_tva")),
        "montant_ttc": _num(data.get("montant_ttc")),
        "devise": "TND",
        "lignes": [l.model_dump() for l in lignes],
    }

    num = data.get("numero_document")
    date_s = data.get("date_document")

    if doc_type == DocumentType.facture:
        base["numero_facture"] = num
        base["date_facture"] = date_s
    elif doc_type == DocumentType.devis:
        base["numero_devis"] = num
        base["date_devis"] = date_s
    elif doc_type == DocumentType.bon_livraison:
        base["numero_bl"] = num
        base["date_livraison"] = date_s
    elif doc_type == DocumentType.bon_commande:
        base["numero_bc"] = num
        base["date_commande"] = date_s
    elif doc_type == DocumentType.avoir:
        base["numero_avoir"] = num
        base["date_avoir"] = date_s

    return base


def _empty_structure(doc_type: DocumentType) -> dict:
    """Return empty structure for given type."""
    if doc_type == DocumentType.facture:
        return ExtractedFacture(lignes=[]).model_dump()
    if doc_type == DocumentType.devis:
        return ExtractedDevis(lignes=[]).model_dump()
    if doc_type == DocumentType.bon_livraison:
        return ExtractedBonLivraison(lignes=[]).model_dump()
    if doc_type == DocumentType.bon_commande:
        return ExtractedBonCommande(lignes=[]).model_dump()
    if doc_type == DocumentType.avoir:
        return ExtractedAvoir().model_dump()
    return {"lignes": []}


# ============================================================
# HELPERS
# ============================================================

def _to_decimal(value: Optional[str]) -> Optional[Decimal]:
    return _clean_decimal(value) if value else None


def _clean_decimal(value: Optional[str]) -> Optional[Decimal]:
    if not value:
        return None
    cleaned = re.sub(r"[^\d,.]", "", str(value))
    # Handle French format: 1.234,56 -> 1234.56
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        return Decimal(cleaned)
    except Exception:
        return None


def _to_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d",
                "%d/%m/%y", "%d-%m-%y", "%d.%m.%y"):
        try:
            from datetime import datetime
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None
