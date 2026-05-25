"""
SQLAlchemy ORM models — mirrors database/schema.sql
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Date,
    DateTime, Numeric, ForeignKey, Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from database import Base
import enum


class DocumentTypeEnum(str, enum.Enum):
    facture      = "facture"
    bon_livraison = "bon_livraison"
    bon_commande  = "bon_commande"
    avoir        = "avoir"
    devis        = "devis"


class DocumentStatusEnum(str, enum.Enum):
    pending    = "pending"
    classified = "classified"
    extracted  = "extracted"
    error      = "error"


# ─── Fournisseur ───────────────────────────────────────────────

class Fournisseur(Base):
    __tablename__ = "fournisseurs"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nom        = Column(String(255), nullable=False)
    siret      = Column(String(14))
    adresse    = Column(Text)
    email      = Column(String(255))
    telephone  = Column(String(20))
    metadata_  = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


# ─── Document ──────────────────────────────────────────────────

class Document(Base):
    __tablename__ = "documents"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nom_fichier      = Column(String(500), nullable=False)
    storage_url      = Column(Text, nullable=False)
    thumbnail_url    = Column(Text)
    type_document    = Column(SAEnum(DocumentTypeEnum, name="document_type", create_type=False))
    statut           = Column(
        SAEnum(DocumentStatusEnum, name="document_status", create_type=False),
        default=DocumentStatusEnum.extracted,
    )
    score_confiance  = Column(Numeric(5, 4))
    fournisseur_id   = Column(UUID(as_uuid=True), ForeignKey("fournisseurs.id", ondelete="SET NULL"))
    metadata_        = Column("metadata", JSONB, default=dict)
    created_at       = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at       = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    fournisseur = relationship("Fournisseur", foreign_keys=[fournisseur_id])
    facture     = relationship("Facture",     back_populates="document", uselist=False, cascade="all, delete-orphan")
    devis_      = relationship("Devis",       back_populates="document", uselist=False, cascade="all, delete-orphan")
    bon_commande = relationship("BonCommande", back_populates="document", uselist=False, cascade="all, delete-orphan")
    bon_livraison = relationship("BonLivraison", back_populates="document", uselist=False, cascade="all, delete-orphan")
    avoir_       = relationship("Avoir",      back_populates="document", uselist=False, cascade="all, delete-orphan")


# ─── Facture ───────────────────────────────────────────────────

class Facture(Base):
    __tablename__ = "factures"

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id        = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    numero_facture     = Column(String(100))
    date_facture       = Column(Date)
    date_echeance      = Column(Date)
    fournisseur_id     = Column(UUID(as_uuid=True), ForeignKey("fournisseurs.id", ondelete="SET NULL"))
    montant_ht         = Column(Numeric(12, 3))
    tva_taux           = Column(Numeric(5, 2), default=Decimal("19.0"))
    montant_tva        = Column(Numeric(12, 3))
    montant_ttc        = Column(Numeric(12, 3))
    devise             = Column(String(3), default="TND")
    reference_commande = Column(String(100))
    designation        = Column(Text)
    notes              = Column(Text)
    created_at         = Column(DateTime(timezone=True), default=datetime.utcnow)

    document = relationship("Document", back_populates="facture")
    lignes   = relationship("LigneFacture", back_populates="facture", cascade="all, delete-orphan")


class LigneFacture(Base):
    __tablename__ = "lignes_facture"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facture_id    = Column(UUID(as_uuid=True), ForeignKey("factures.id", ondelete="CASCADE"), nullable=False)
    reference     = Column(String(200))
    designation   = Column(Text, nullable=False)
    quantite      = Column(Numeric(10, 3))
    unite         = Column(String(20))
    prix_unitaire = Column(Numeric(12, 4))
    remise_pct    = Column(Numeric(5, 2), default=Decimal("0"))
    montant_ht    = Column(Numeric(12, 3))
    tva_taux      = Column(Numeric(5, 2))
    montant_ttc   = Column(Numeric(12, 3))
    position      = Column(Integer, default=0)

    facture = relationship("Facture", back_populates="lignes")


# ─── Devis ─────────────────────────────────────────────────────

class Devis(Base):
    __tablename__ = "devis"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id    = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    numero_devis   = Column(String(100))
    date_devis     = Column(Date)
    date_validite  = Column(Date)
    fournisseur_id = Column(UUID(as_uuid=True), ForeignKey("fournisseurs.id", ondelete="SET NULL"))
    montant_ht     = Column(Numeric(12, 3))
    montant_ttc    = Column(Numeric(12, 3))
    devise         = Column(String(3), default="TND")
    conditions     = Column(Text)
    notes          = Column(Text)
    created_at     = Column(DateTime(timezone=True), default=datetime.utcnow)

    document = relationship("Document", back_populates="devis_")
    lignes   = relationship("LigneDevis", back_populates="devis", cascade="all, delete-orphan")


class LigneDevis(Base):
    __tablename__ = "lignes_devis"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    devis_id      = Column(UUID(as_uuid=True), ForeignKey("devis.id", ondelete="CASCADE"), nullable=False)
    reference     = Column(String(200))
    designation   = Column(Text, nullable=False)
    quantite      = Column(Numeric(10, 3))
    unite         = Column(String(20))
    prix_unitaire = Column(Numeric(12, 4))
    remise_pct    = Column(Numeric(5, 2), default=Decimal("0"))
    montant_ht    = Column(Numeric(12, 3))
    montant_ttc   = Column(Numeric(12, 3))
    marque        = Column(String(255))
    puissance_wc  = Column(Numeric(8, 2))
    position      = Column(Integer, default=0)

    devis = relationship("Devis", back_populates="lignes")


# ─── Bon de commande ───────────────────────────────────────────

class BonCommande(Base):
    __tablename__ = "bons_commande"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id         = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    numero_bc           = Column(String(100))
    date_commande       = Column(Date)
    date_livraison_prev = Column(Date)
    fournisseur_id      = Column(UUID(as_uuid=True), ForeignKey("fournisseurs.id", ondelete="SET NULL"))
    montant_ht          = Column(Numeric(12, 3))
    montant_ttc         = Column(Numeric(12, 3))
    devise              = Column(String(3), default="TND")
    adresse_livraison   = Column(Text)
    conditions_paiement = Column(Text)
    notes               = Column(Text)
    created_at          = Column(DateTime(timezone=True), default=datetime.utcnow)

    document = relationship("Document", back_populates="bon_commande")


# ─── Bon de livraison ──────────────────────────────────────────

class BonLivraison(Base):
    __tablename__ = "bons_livraison"

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id        = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    numero_bl          = Column(String(100))
    date_livraison     = Column(Date)
    fournisseur_id     = Column(UUID(as_uuid=True), ForeignKey("fournisseurs.id", ondelete="SET NULL"))
    adresse_livraison  = Column(Text)
    reference_commande = Column(String(100))
    transporteur       = Column(String(255))
    numero_suivi       = Column(String(255))
    notes              = Column(Text)
    created_at         = Column(DateTime(timezone=True), default=datetime.utcnow)

    document = relationship("Document", back_populates="bon_livraison")


# ─── Avoir ─────────────────────────────────────────────────────

class Avoir(Base):
    __tablename__ = "avoirs"

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id        = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    numero_avoir       = Column(String(100))
    date_avoir         = Column(Date)
    facture_reference  = Column(String(100))
    fournisseur_id     = Column(UUID(as_uuid=True), ForeignKey("fournisseurs.id", ondelete="SET NULL"))
    montant_ht         = Column(Numeric(12, 3))
    montant_ttc        = Column(Numeric(12, 3))
    devise             = Column(String(3), default="TND")
    motif              = Column(Text)
    notes              = Column(Text)
    created_at         = Column(DateTime(timezone=True), default=datetime.utcnow)

    document = relationship("Document", back_populates="avoir_")
