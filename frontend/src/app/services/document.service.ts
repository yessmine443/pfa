import { Injectable, signal, computed } from '@angular/core';
import { Observable, tap, catchError } from 'rxjs';
import { ApiService } from './api.service';
import {
  DocumentCard, DocumentType, DocumentStatus,
  ClassifyResponse, ExtractResponse, CompareResponse, CompareRequest,
} from '../models/document.model';

@Injectable({ providedIn: 'root' })
export class DocumentService {
  // ---- Reactive state (Angular Signals) ----
  private _documents = signal<DocumentCard[]>([]);
  private _loading = signal(false);
  private _error = signal<string | null>(null);
  private _activeFilter = signal<DocumentType | 'all'>('all');

  // ---- Public computed ----
  readonly documents = this._documents.asReadonly();
  readonly loading = this._loading.asReadonly();
  readonly error = this._error.asReadonly();
  readonly activeFilter = this._activeFilter.asReadonly();

  readonly filteredDocuments = computed(() => {
    const filter = this._activeFilter();
    const docs = this._documents();
    if (filter === 'all') return docs;
    return docs.filter(d => d.type_document === filter);
  });

  readonly stats = computed(() => {
    const docs = this._documents();
    return {
      total: docs.length,
      factures: docs.filter(d => d.type_document === 'facture').length,
      bons_livraison: docs.filter(d => d.type_document === 'bon_livraison').length,
      bons_commande: docs.filter(d => d.type_document === 'bon_commande').length,
      avoirs: docs.filter(d => d.type_document === 'avoir').length,
      devis: docs.filter(d => d.type_document === 'devis').length,
      pending: docs.filter(d => d.statut === 'pending').length,
      errors: docs.filter(d => d.statut === 'error').length,
    };
  });

  private readonly STORAGE_KEY = 'sparky_documents';

  constructor(private api: ApiService) {
    this._loadFromDb();
  }

  /** Charge les documents depuis PostgreSQL via l'API. Fallback sur localStorage. */
  private _loadFromDb(): void {
    this._loading.set(true);
    this.api.getDocuments().subscribe({
      next: (docs: any[]) => {
        const cards: DocumentCard[] = docs.map(d => ({
          document_id:    d.document_id,
          nom_fichier:    d.nom_fichier,
          storage_url:    d.storage_url ?? '',
          statut:         d.statut as DocumentStatus,
          type_document:  d.type_document,
          score_confiance: d.score_confiance,
          fournisseur_nom: d.fournisseur_nom,
          montant_ttc:    d.montant_ttc,
          numero_document: d.numero_document,
          lignes:         d.lignes ?? [],
          created_at:     d.created_at,
        }));
        this._documents.set(cards);
        this._saveToStorage(cards);   // sync localStorage aussi
        this._loading.set(false);
      },
      error: () => {
        // API indisponible → fallback localStorage
        this._loadFromStorage();
        this._loading.set(false);
      },
    });
  }

  /** Recharge la liste depuis PostgreSQL (après un nouveau scan par exemple). */
  refreshFromDb(): void {
    this._loadFromDb();
  }

  private _loadFromStorage(): void {
    try {
      const raw = localStorage.getItem(this.STORAGE_KEY);
      if (raw) {
        const docs: DocumentCard[] = JSON.parse(raw);
        this._documents.set(docs);
      }
    } catch { /* ignore parse errors */ }
  }

  private _saveToStorage(docs: DocumentCard[]): void {
    try {
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(docs));
    } catch { /* ignore quota errors */ }
  }

  // ---- Filter ----

  setFilter(filter: DocumentType | 'all'): void {
    this._activeFilter.set(filter);
  }

  // ---- Upload + process ----

  processFile(file: File): Observable<{ classify: ClassifyResponse; extract: ExtractResponse }> {
    this._loading.set(true);
    this._error.set(null);

    return this.api.processDocument(file).pipe(
      tap(result => {
        // Ajout immédiat en local pour feedback rapide
        const card = this._buildCard(result);
        this._documents.update(docs => {
          const updated = [card, ...docs];
          this._saveToStorage(updated);
          return updated;
        });
        this._loading.set(false);
        // Puis synchronisation avec PostgreSQL
        this.refreshFromDb();
      }),
      catchError(err => {
        this._error.set(err.message);
        this._loading.set(false);
        throw err;
      }),
    );
  }

  // ---- Upload only (no classify/extract) ----

  uploadFile(file: File): Observable<any> {
    this._loading.set(true);
    return this.api.uploadDocument(file).pipe(
      tap(result => {
        const card: DocumentCard = {
          document_id: result.document_id,
          nom_fichier: result.nom_fichier,
          storage_url: result.storage_url,
          statut: 'pending',
          created_at: new Date().toISOString(),
        };
        this._documents.update(docs => [card, ...docs]);
        this._loading.set(false);
      }),
      catchError(err => {
        this._error.set(err.message);
        this._loading.set(false);
        throw err;
      }),
    );
  }

  // ---- Compare devis ----

  comparePrices(payload: CompareRequest): Observable<CompareResponse> {
    return this.api.comparePrices(payload);
  }

  // ---- Remove ----

  removeDocument(documentId: string): void {
    this.api.deleteDocument(documentId).subscribe({
      next: () => {
        this._documents.update(docs => {
          const updated = docs.filter(d => d.document_id !== documentId);
          this._saveToStorage(updated);
          return updated;
        });
      },
      error: (err) => {
        this._error.set('Suppression impossible: ' + (err?.message ?? err));
      },
    });
  }

  // ---- Clear error ----

  clearError(): void {
    this._error.set(null);
  }

  // ---- Helpers ----

  private _buildCard(result: any): DocumentCard {
    return {
      document_id: result.upload?.document_id ?? result.document_id,
      nom_fichier: result.upload?.nom_fichier ?? 'document',
      storage_url: result.upload?.storage_url ?? '',
      statut: 'extracted' as DocumentStatus,
      type_document: result.classification?.type_document,
      score_confiance: result.classification?.score_confiance,
      fournisseur_nom: result.extraction?.donnees?.fournisseur_nom,
      montant_ttc: result.extraction?.donnees?.montant_ttc,
      numero_document:
        result.extraction?.donnees?.numero_facture ||
        result.extraction?.donnees?.numero_devis ||
        result.extraction?.donnees?.numero_bl ||
        result.extraction?.donnees?.numero_bc ||
        result.extraction?.donnees?.numero_avoir,
      lignes: result.extraction?.donnees?.lignes || [],
      created_at: new Date().toISOString(),
    };
  }
}
