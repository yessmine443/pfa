import { Component, OnInit, signal, computed } from '@angular/core';
import { ApiService } from '../../services/api.service';
import { DocumentService } from '../../services/document.service';
import { DocumentCard, LigneDocument } from '../../models/document.model';
import { of } from 'rxjs';
import { catchError } from 'rxjs/operators';

// â”€â”€ Types â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export interface DocResult {
  id: string;
  nom_fichier: string;
  fournisseur: string;
  type: string;
  lignes: LigneDocument[];
  loading: boolean;
  error: string | null;
}

export interface ArticleRow {
  designation: string;          // normalized key for grouping
  items: ArticleCell[];         // one per fournisseur
  stockQty: number | null;
}

export interface ArticleCell {
  fournisseur: string;
  ligne: LigneDocument | null;
}

// â”€â”€ Component â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@Component({
  standalone: false,
  selector: 'app-price-comparison',
  templateUrl: './price-comparison.component.html',
  styleUrls: ['./price-comparison.component.scss'],
})
export class PriceComparisonComponent implements OnInit {

  // â”€â”€ state â”€â”€
  existingDocs   = signal<DocumentCard[]>([]);
  selectedIds    = signal<Set<string>>(new Set());
  docResults     = signal<DocResult[]>([]);
  isDragging     = signal(false);
  globalError    = signal<string | null>(null);
  stockMap       = signal<Map<string, number>>(new Map());

  // â”€â”€ computed â”€â”€
  fournisseurs = computed(() =>
    [...new Set(this.docResults().map(d => d.fournisseur).filter(Boolean))]
  );

  articleRows = computed((): ArticleRow[] => {
    const docs = this.docResults().filter(d => !d.loading && !d.error);
    if (docs.length < 1) return [];

    const fournisseurs = this.fournisseurs();
    const stockMap     = this.stockMap();

    // Group articles by normalized designation
    const groupMap = new Map<string, Map<string, LigneDocument>>();

    for (const doc of docs) {
      for (const ligne of doc.lignes) {
        const key = this._normalize(ligne.designation);
        if (!groupMap.has(key)) groupMap.set(key, new Map());
        groupMap.get(key)!.set(doc.fournisseur, ligne);
      }
    }

    const rows: ArticleRow[] = [];
    groupMap.forEach((byFourn, key) => {
      const items: ArticleCell[] = fournisseurs.map(f => ({
        fournisseur: f,
        ligne: byFourn.get(f) ?? null,
      }));
      rows.push({
        designation: key,
        items,
        stockQty: stockMap.get(key) ?? null,
      });
    });

    return rows;
  });

  anyLoading = computed(() => this.docResults().some(d => d.loading));

  // â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  constructor(
    private api: ApiService,
    private docService: DocumentService,
  ) {}

  ngOnInit(): void {
    this.existingDocs.set(
      this.docService.documents().filter(d =>
        d.statut === 'extracted' &&
        (d.type_document === 'devis' || d.type_document === 'facture' ||
         d.type_document === 'bon_commande')
      )
    );
    this._loadStock();
  }

  // â”€â”€ Import from existing documents â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  toggleExistingDoc(doc: DocumentCard): void {
    const next = new Set(this.selectedIds());
    if (next.has(doc.document_id)) {
      next.delete(doc.document_id);
      this.docResults.update(r => r.filter(d => d.id !== doc.document_id));
    } else {
      next.add(doc.document_id);
      this._addExistingDoc(doc);
    }
    this.selectedIds.set(next);
  }

  isSelected(doc: DocumentCard): boolean {
    return this.selectedIds().has(doc.document_id);
  }

  private _addExistingDoc(doc: DocumentCard): void {
    const lignes = doc.lignes || [];
    const result: DocResult = {
      id: doc.document_id,
      nom_fichier: doc.nom_fichier,
      fournisseur: doc.fournisseur_nom || doc.nom_fichier.replace(/\.[^.]+$/, ''),
      type: doc.type_document || 'devis',
      lignes,
      loading: false,
      error: lignes.length === 0 ? 'Aucun article extrait â€” rÃ©-importez ce fichier.' : null,
    };
    this.docResults.update(r => [...r, result]);
  }

  // â”€â”€ File drag & drop / upload â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  onDragOver(e: DragEvent): void {
    e.preventDefault();
    this.isDragging.set(true);
  }

  onDragLeave(): void { this.isDragging.set(false); }

  onDrop(e: DragEvent): void {
    e.preventDefault();
    this.isDragging.set(false);
    const files = Array.from(e.dataTransfer?.files || []);
    this._processFiles(files);
  }

  onFilePick(e: Event): void {
    const input = e.target as HTMLInputElement;
    const files = Array.from(input.files || []);
    this._processFiles(files);
    input.value = '';
  }

  private _processFiles(files: File[]): void {
    for (const file of files) {
      const id = 'file-' + Math.random().toString(36).slice(2);
      const placeholder: DocResult = {
        id,
        nom_fichier: file.name,
        fournisseur: file.name.replace(/\.[^.]+$/, ''),
        type: 'devis',
        lignes: [],
        loading: true,
        error: null,
      };
      this.docResults.update(r => [...r, placeholder]);

      this.api.processDocument(file).subscribe({
        next: (res: any) => {
          const lignes: LigneDocument[] = res.extraction?.donnees?.lignes || [];
          const fournisseur = res.extraction?.donnees?.fournisseur_nom || placeholder.fournisseur;
          const type = res.classification?.type_document || 'devis';
          this.docResults.update(r => r.map(d =>
            d.id === id ? { ...d, loading: false, lignes, fournisseur, type } : d
          ));
        },
        error: (err: any) => {
          this.docResults.update(r => r.map(d =>
            d.id === id ? { ...d, loading: false, error: err.message } : d
          ));
        },
      });
    }
  }

  // â”€â”€ Remove doc â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  removeDoc(id: string): void {
    this.docResults.update(r => r.filter(d => d.id !== id));
    const next = new Set(this.selectedIds());
    next.delete(id);
    this.selectedIds.set(next);
  }

  // â”€â”€ Fournisseur name edit â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  updateFournisseur(id: string, value: string): void {
    this.docResults.update(r => r.map(d =>
      d.id === id ? { ...d, fournisseur: value } : d
    ));
  }

  // â”€â”€ Reset â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  reset(): void {
    this.docResults.set([]);
    this.selectedIds.set(new Set());
    this.globalError.set(null);
  }

  // â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  bestPrice(row: ArticleRow): number | null {
    const prices = row.items
      .map(i => i.ligne?.prix_unitaire != null ? Number(i.ligne.prix_unitaire) : null)
      .filter((p): p is number => p != null && p > 0);
    return prices.length ? Math.min(...prices) : null;
  }

  isBest(cell: ArticleCell, row: ArticleRow): boolean {
    const best = this.bestPrice(row);
    if (best === null || cell.ligne?.prix_unitaire == null) return false;
    return Math.abs(Number(cell.ligne.prix_unitaire) - best) < 0.0001;
  }

  getDocResult(id: string): DocResult | undefined {
    return this.docResults().find(d => d.id === id);
  }

  totalParFournisseur(fournisseur: string): number {
    const doc = this.docResults().find(d => d.fournisseur === fournisseur);
    if (!doc) return 0;
    return doc.lignes.reduce((acc, l) => {
      const pu  = Number(l.prix_unitaire  ?? 0);
      const qty = Number(l.quantite       ?? 1);
      const rem = Number(l.remise_pct     ?? 0);
      const tva = Number(l.tva_taux       ?? 0);
      const ht  = pu * qty * (1 - rem / 100);
      return acc + ht * (1 + tva / 100);
    }, 0);
  }

  isBestTotal(fournisseur: string): boolean {
    const totals = this.fournisseurs().map(f => this.totalParFournisseur(f)).filter(t => t > 0);
    if (!totals.length) return false;
    const best = Math.min(...totals);
    return Math.abs(this.totalParFournisseur(fournisseur) - best) < 0.001;
  }

  private _normalize(s: string): string {
    return s.trim().toLowerCase().replace(/\s+/g, ' ');
  }

  private _loadStock(): void {
    this.api.getComparaisonPrix().pipe(
      catchError(() => of(null))
    ).subscribe(res => {
      if (!res) return;
      const map = new Map<string, number>();
      for (const article of res.articles) {
        map.set(this._normalize(article.nom_normalise), article.quantite_stock);
      }
      this.stockMap.set(map);
    });
  }
}
