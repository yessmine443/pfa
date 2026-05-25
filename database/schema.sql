-- ============================================================
-- SPARKY - Photovoltaiques Document Management System
-- PostgreSQL Schema
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================
-- TABLE: users (Authentication)
-- ============================================================

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    nom             VARCHAR(255),
    role            VARCHAR(50) DEFAULT 'user',
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);

-- Seed admin user (password: admin123 — bcrypt hash)
INSERT INTO users (email, password_hash, nom, role) VALUES
    ('admin@sparky.tn', '$2b$12$pOuNp.FLGFUcDPWWOLoVTefX03Q3RRmUO5bjzMvTLKBt4dTIlirjS', 'Admin SPARKY', 'admin');


-- ============================================================
-- ENUM TYPES
-- ============================================================

CREATE TYPE document_type AS ENUM (
    'facture',
    'bon_livraison',
    'bon_commande',
    'avoir',
    'devis'
);

CREATE TYPE document_status AS ENUM (
    'pending',
    'classified',
    'extracted',
    'error'
);

-- ============================================================
-- TABLE: fournisseurs (Suppliers)
-- ============================================================

CREATE TABLE fournisseurs (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nom         VARCHAR(255) NOT NULL,
    siret       VARCHAR(14),
    adresse     TEXT,
    email       VARCHAR(255),
    telephone   VARCHAR(20),
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_fournisseurs_nom ON fournisseurs USING gin(nom gin_trgm_ops);

-- ============================================================
-- TABLE: documents (Master document table)
-- ============================================================

CREATE TABLE documents (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nom_fichier         VARCHAR(500) NOT NULL,
    storage_url         TEXT NOT NULL,
    thumbnail_url       TEXT,
    type_document       document_type,
    statut              document_status DEFAULT 'pending',
    score_confiance     DECIMAL(5,4),          -- 0.0000 to 1.0000
    fournisseur_id      UUID REFERENCES fournisseurs(id) ON DELETE SET NULL,
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_documents_type ON documents(type_document);
CREATE INDEX idx_documents_statut ON documents(statut);
CREATE INDEX idx_documents_fournisseur ON documents(fournisseur_id);
CREATE INDEX idx_documents_created_at ON documents(created_at DESC);
CREATE INDEX idx_documents_metadata ON documents USING gin(metadata);

-- ============================================================
-- TABLE: factures
-- ============================================================

CREATE TABLE factures (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id         UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    numero_facture      VARCHAR(100),
    date_facture        DATE,
    date_echeance       DATE,
    fournisseur_id      UUID REFERENCES fournisseurs(id) ON DELETE SET NULL,
    montant_ht          DECIMAL(12,2),
    tva_taux            DECIMAL(5,2) DEFAULT 20.00,
    montant_tva         DECIMAL(12,2),
    montant_ttc         DECIMAL(12,2),
    devise              VARCHAR(3) DEFAULT 'EUR',
    reference_commande  VARCHAR(100),
    designation         TEXT,
    notes               TEXT,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_factures_document ON factures(document_id);
CREATE INDEX idx_factures_numero ON factures(numero_facture);
CREATE INDEX idx_factures_date ON factures(date_facture DESC);

-- ============================================================
-- TABLE: lignes_facture (Invoice line items)
-- ============================================================

CREATE TABLE lignes_facture (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    facture_id      UUID NOT NULL REFERENCES factures(id) ON DELETE CASCADE,
    reference       VARCHAR(200),
    designation     TEXT NOT NULL,
    quantite        DECIMAL(10,3),
    unite           VARCHAR(20),
    prix_unitaire   DECIMAL(12,4),
    remise_pct      DECIMAL(5,2) DEFAULT 0,
    montant_ht      DECIMAL(12,2),
    tva_taux        DECIMAL(5,2),
    position        INTEGER DEFAULT 0
);

CREATE INDEX idx_lignes_facture_facture ON lignes_facture(facture_id);

-- ============================================================
-- TABLE: bons_livraison (Delivery notes)
-- ============================================================

CREATE TABLE bons_livraison (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id         UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    numero_bl           VARCHAR(100),
    date_livraison      DATE,
    fournisseur_id      UUID REFERENCES fournisseurs(id) ON DELETE SET NULL,
    adresse_livraison   TEXT,
    reference_commande  VARCHAR(100),
    transporteur        VARCHAR(255),
    numero_suivi        VARCHAR(255),
    notes               TEXT,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_bl_document ON bons_livraison(document_id);
CREATE INDEX idx_bl_numero ON bons_livraison(numero_bl);

-- ============================================================
-- TABLE: lignes_bl (Delivery note line items)
-- ============================================================

CREATE TABLE lignes_bl (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bl_id           UUID NOT NULL REFERENCES bons_livraison(id) ON DELETE CASCADE,
    reference       VARCHAR(200),
    designation     TEXT NOT NULL,
    quantite_cmd    DECIMAL(10,3),
    quantite_livree DECIMAL(10,3),
    unite           VARCHAR(20),
    position        INTEGER DEFAULT 0
);

CREATE INDEX idx_lignes_bl_bl ON lignes_bl(bl_id);

-- ============================================================
-- TABLE: bons_commande (Purchase orders)
-- ============================================================

CREATE TABLE bons_commande (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id         UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    numero_bc           VARCHAR(100),
    date_commande       DATE,
    date_livraison_prev DATE,
    fournisseur_id      UUID REFERENCES fournisseurs(id) ON DELETE SET NULL,
    montant_ht          DECIMAL(12,2),
    montant_ttc         DECIMAL(12,2),
    devise              VARCHAR(3) DEFAULT 'EUR',
    adresse_livraison   TEXT,
    conditions_paiement TEXT,
    notes               TEXT,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_bc_document ON bons_commande(document_id);
CREATE INDEX idx_bc_numero ON bons_commande(numero_bc);

-- ============================================================
-- TABLE: avoirs (Credit notes)
-- ============================================================

CREATE TABLE avoirs (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id         UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    numero_avoir        VARCHAR(100),
    date_avoir          DATE,
    facture_reference   VARCHAR(100),
    fournisseur_id      UUID REFERENCES fournisseurs(id) ON DELETE SET NULL,
    montant_ht          DECIMAL(12,2),
    montant_ttc         DECIMAL(12,2),
    devise              VARCHAR(3) DEFAULT 'EUR',
    motif               TEXT,
    notes               TEXT,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_avoirs_document ON avoirs(document_id);
CREATE INDEX idx_avoirs_numero ON avoirs(numero_avoir);

-- ============================================================
-- TABLE: devis (Quotations)
-- ============================================================

CREATE TABLE devis (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id         UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    numero_devis        VARCHAR(100),
    date_devis          DATE,
    date_validite       DATE,
    fournisseur_id      UUID REFERENCES fournisseurs(id) ON DELETE SET NULL,
    montant_ht          DECIMAL(12,2),
    montant_ttc         DECIMAL(12,2),
    devise              VARCHAR(3) DEFAULT 'EUR',
    conditions          TEXT,
    notes               TEXT,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_devis_document ON devis(document_id);
CREATE INDEX idx_devis_numero ON devis(numero_devis);
CREATE INDEX idx_devis_date ON devis(date_devis DESC);

-- ============================================================
-- TABLE: lignes_devis (Quotation line items)
-- ============================================================

CREATE TABLE lignes_devis (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    devis_id        UUID NOT NULL REFERENCES devis(id) ON DELETE CASCADE,
    reference       VARCHAR(200),
    designation     TEXT NOT NULL,
    quantite        DECIMAL(10,3),
    unite           VARCHAR(20),
    prix_unitaire   DECIMAL(12,4),
    remise_pct      DECIMAL(5,2) DEFAULT 0,
    montant_ht      DECIMAL(12,2),
    marque          VARCHAR(255),
    puissance_wc    DECIMAL(8,2),       -- Watts-crête (photovoltaic)
    rendement_pct   DECIMAL(5,2),       -- Panel efficiency %
    position        INTEGER DEFAULT 0
);

CREATE INDEX idx_lignes_devis_devis ON lignes_devis(devis_id);

-- ============================================================
-- TABLE: comparaisons_devis (Price comparisons between quotes)
-- ============================================================

CREATE TABLE comparaisons_devis (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reference_produit VARCHAR(500) NOT NULL,
    designation     TEXT,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE comparaisons_devis_items (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    comparaison_id      UUID NOT NULL REFERENCES comparaisons_devis(id) ON DELETE CASCADE,
    devis_id            UUID NOT NULL REFERENCES devis(id) ON DELETE CASCADE,
    fournisseur_id      UUID REFERENCES fournisseurs(id),
    prix_unitaire       DECIMAL(12,4),
    quantite            DECIMAL(10,3),
    montant_total       DECIMAL(12,2),
    est_meilleur_prix   BOOLEAN DEFAULT FALSE,
    devise              VARCHAR(3) DEFAULT 'EUR'
);

CREATE INDEX idx_comparaisons_items_comp ON comparaisons_devis_items(comparaison_id);
CREATE INDEX idx_comparaisons_items_devis ON comparaisons_devis_items(devis_id);

-- ============================================================
-- TABLE: classifications_log (AI classification audit trail)
-- ============================================================

CREATE TABLE classifications_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    type_predit     document_type,
    score_confiance DECIMAL(5,4),
    top_predictions JSONB,              -- Array of {type, score}
    modele_version  VARCHAR(50),
    duree_ms        INTEGER,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_classif_log_document ON classifications_log(document_id);

-- ============================================================
-- TABLE: articles (Catalogue canonique des produits)
-- Un seul enregistrement par produit, peu importe le fournisseur.
-- ============================================================

CREATE TABLE articles (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reference_interne   VARCHAR(100) UNIQUE NOT NULL,   -- code interne normalisé ex: COLLIER-PLAST-250x4.7
    nom_normalise       TEXT NOT NULL,                  -- nom canonique lisible
    categorie           VARCHAR(100),                   -- Câbles, Panneaux photovoltaïque, Structure métallique…
    unite_mesure        VARCHAR(20),                    -- pièce(s), Métre, etc.
    specifications      JSONB DEFAULT '{}',             -- {section_mm2, couleur, longueur_mm, largeur_mm, puissance_wc, tension_v, …}
    description         TEXT,
    actif               BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_articles_reference    ON articles(reference_interne);
CREATE INDEX idx_articles_categorie    ON articles(categorie);
CREATE INDEX idx_articles_nom          ON articles USING gin(nom_normalise gin_trgm_ops);
CREATE INDEX idx_articles_specs        ON articles USING gin(specifications);

-- ============================================================
-- TABLE: articles_fournisseurs (Correspondances fournisseur → article canonique)
-- Chaque fournisseur peut avoir son propre nom/référence pour le même article.
-- ============================================================

CREATE TABLE articles_fournisseurs (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id          UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    fournisseur_id      UUID NOT NULL REFERENCES fournisseurs(id) ON DELETE CASCADE,
    reference_fournisseur VARCHAR(200),                 -- référence chez ce fournisseur
    nom_fournisseur     TEXT NOT NULL,                  -- désignation telle qu'elle apparaît sur la facture
    prix_achat          DECIMAL(12,4),
    prix_vente          DECIMAL(12,4),
    marge_pct           DECIMAL(5,2),
    tva_taux            DECIMAL(5,2) DEFAULT 19.0,
    marque              VARCHAR(255),
    score_similarite    DECIMAL(5,4) DEFAULT 1.0,       -- 1.0 = correspondance exacte confirmée
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (fournisseur_id, reference_fournisseur)
);

CREATE INDEX idx_artfourn_article      ON articles_fournisseurs(article_id);
CREATE INDEX idx_artfourn_fournisseur  ON articles_fournisseurs(fournisseur_id);
CREATE INDEX idx_artfourn_ref          ON articles_fournisseurs(reference_fournisseur);
CREATE INDEX idx_artfourn_nom          ON articles_fournisseurs USING gin(nom_fournisseur gin_trgm_ops);

-- ============================================================
-- TABLE: mouvements_stock (Entrées / sorties par document source)
-- La quantité totale d'un article = SUM(quantite) sur ses mouvements.
-- ============================================================

CREATE TYPE mouvement_type AS ENUM ('entree', 'sortie', 'correction');

CREATE TABLE mouvements_stock (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id          UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    fournisseur_id      UUID REFERENCES fournisseurs(id) ON DELETE SET NULL,
    document_id         UUID REFERENCES documents(id) ON DELETE SET NULL,  -- facture / BL source
    type_mouvement      mouvement_type NOT NULL DEFAULT 'entree',
    quantite            DECIMAL(12,4) NOT NULL,                            -- positif = entree, négatif = sortie
    prix_unitaire       DECIMAL(12,4),
    date_mouvement      DATE NOT NULL DEFAULT CURRENT_DATE,
    notes               TEXT,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_mvt_article      ON mouvements_stock(article_id);
CREATE INDEX idx_mvt_document     ON mouvements_stock(document_id);
CREATE INDEX idx_mvt_fournisseur  ON mouvements_stock(fournisseur_id);
CREATE INDEX idx_mvt_date         ON mouvements_stock(date_mouvement DESC);

-- ============================================================
-- VIEW: v_stock_articles  (quantité totale par article)
-- ============================================================

CREATE VIEW v_stock_articles AS
SELECT
    a.id,
    a.reference_interne,
    a.nom_normalise,
    a.categorie,
    a.unite_mesure,
    a.specifications,
    COALESCE(SUM(
        CASE m.type_mouvement
            WHEN 'entree'     THEN  m.quantite
            WHEN 'sortie'     THEN -m.quantite
            WHEN 'correction' THEN  m.quantite
        END
    ), 0) AS quantite_totale,
    COUNT(DISTINCT m.fournisseur_id) AS nb_fournisseurs,
    MAX(m.date_mouvement)            AS derniere_entree
FROM articles a
LEFT JOIN mouvements_stock m ON m.article_id = a.id
WHERE a.actif = TRUE
GROUP BY a.id, a.reference_interne, a.nom_normalise, a.categorie, a.unite_mesure, a.specifications;

-- ============================================================
-- VIEW: v_stock_par_fournisseur  (quantité par article ET fournisseur)
-- ============================================================

CREATE VIEW v_stock_par_fournisseur AS
SELECT
    a.id            AS article_id,
    a.reference_interne,
    a.nom_normalise,
    a.categorie,
    f.id            AS fournisseur_id,
    f.nom           AS fournisseur_nom,
    af.nom_fournisseur,
    af.reference_fournisseur,
    af.prix_achat,
    af.prix_vente,
    COALESCE(SUM(
        CASE m.type_mouvement
            WHEN 'entree'     THEN  m.quantite
            WHEN 'sortie'     THEN -m.quantite
            WHEN 'correction' THEN  m.quantite
        END
    ), 0) AS quantite,
    a.unite_mesure
FROM articles a
JOIN articles_fournisseurs af ON af.article_id = a.id
JOIN fournisseurs f ON f.id = af.fournisseur_id
LEFT JOIN mouvements_stock m ON m.article_id = a.id AND m.fournisseur_id = f.id
WHERE a.actif = TRUE
GROUP BY a.id, a.reference_interne, a.nom_normalise, a.categorie,
         f.id, f.nom, af.nom_fournisseur, af.reference_fournisseur,
         af.prix_achat, af.prix_vente, a.unite_mesure;

-- ============================================================
-- TRIGGERS: auto-update updated_at
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_fournisseurs_updated_at
    BEFORE UPDATE ON fournisseurs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_articles_updated_at
    BEFORE UPDATE ON articles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_artfourn_updated_at
    BEFORE UPDATE ON articles_fournisseurs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- VIEWS
-- ============================================================

-- Vue: documents avec infos fournisseur et type
CREATE VIEW v_documents_complets AS
SELECT
    d.id,
    d.nom_fichier,
    d.storage_url,
    d.thumbnail_url,
    d.type_document,
    d.statut,
    d.score_confiance,
    d.created_at,
    f.nom AS fournisseur_nom,
    f.siret AS fournisseur_siret,
    CASE d.type_document
        WHEN 'facture'      THEN fa.montant_ttc
        WHEN 'bon_commande' THEN bc.montant_ttc
        WHEN 'avoir'        THEN av.montant_ttc
        WHEN 'devis'        THEN dv.montant_ttc
        ELSE NULL
    END AS montant_ttc,
    CASE d.type_document
        WHEN 'facture'      THEN fa.numero_facture
        WHEN 'bon_livraison'THEN bl.numero_bl
        WHEN 'bon_commande' THEN bc.numero_bc
        WHEN 'avoir'        THEN av.numero_avoir
        WHEN 'devis'        THEN dv.numero_devis
        ELSE NULL
    END AS numero_document
FROM documents d
LEFT JOIN fournisseurs f ON d.fournisseur_id = f.id
LEFT JOIN factures fa ON fa.document_id = d.id
LEFT JOIN bons_livraison bl ON bl.document_id = d.id
LEFT JOIN bons_commande bc ON bc.document_id = d.id
LEFT JOIN avoirs av ON av.document_id = d.id
LEFT JOIN devis dv ON dv.document_id = d.id;

-- Vue: meilleurs prix par devis groupés
CREATE VIEW v_meilleurs_prix AS
SELECT
    cdi.comparaison_id,
    cd.reference_produit,
    cd.designation,
    cdi.fournisseur_id,
    f.nom AS fournisseur_nom,
    cdi.prix_unitaire,
    cdi.montant_total,
    cdi.est_meilleur_prix,
    dv.numero_devis,
    dv.date_devis
FROM comparaisons_devis_items cdi
JOIN comparaisons_devis cd ON cdi.comparaison_id = cd.id
LEFT JOIN fournisseurs f ON cdi.fournisseur_id = f.id
JOIN devis dv ON cdi.devis_id = dv.id
ORDER BY cd.id, cdi.prix_unitaire ASC;

-- ============================================================
-- SEED DATA (exemple de fournisseurs)
-- ============================================================

INSERT INTO fournisseurs (nom, siret, email, telephone) VALUES
    ('SolarTech France',    '12345678901234', 'contact@solartech.fr',    '0123456789'),
    ('PanneauPro',          '98765432109876', 'info@panneaupro.com',     '0987654321'),
    ('EnergieSolaire SAS',  '11122233344455', 'devis@energiesolaire.fr', '0612345678'),
    ('PhotovoltaSud',       '55566677788899', 'commercial@pvsud.fr',     '0467891234');
