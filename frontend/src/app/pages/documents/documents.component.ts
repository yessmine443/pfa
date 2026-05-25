import { Component, computed, signal } from '@angular/core';
import { Router } from '@angular/router';
import { DocumentService } from '../../services/document.service';
import {
  DocumentCard, DocumentType,
  DOCUMENT_TYPE_LABELS, DOCUMENT_TYPE_ICONS, DOCUMENT_TYPE_COLORS,
} from '../../models/document.model';

type SortKey = 'date' | 'montant' | 'type' | 'nom';

@Component({
  standalone: false,
  selector: 'app-documents',
  templateUrl: './documents.component.html',
  styleUrls: ['./documents.component.scss'],
})
export class DocumentsComponent {
  readonly loading = this.docService.loading;
  readonly activeFilter = this.docService.activeFilter;
  readonly stats = this.docService.stats;

  searchQuery = signal('');
  sortKey = signal<SortKey>('date');
  sortAsc = signal(false);

  typeLabels: { [key: string]: string } = DOCUMENT_TYPE_LABELS;
  typeIcons: { [key: string]: string } = DOCUMENT_TYPE_ICONS;
  typeColors: { [key: string]: string } = DOCUMENT_TYPE_COLORS;

  filters: Array<{ label: string; value: DocumentType | 'all'; icon: string }> = [
    { label: 'Tous', value: 'all', icon: 'folder_open' },
    { label: 'Factures', value: 'facture', icon: 'receipt' },
    { label: 'BL', value: 'bon_livraison', icon: 'local_shipping' },
    { label: 'BC', value: 'bon_commande', icon: 'shopping_cart' },
    { label: 'Devis', value: 'devis', icon: 'request_quote' },
    { label: 'Avoirs', value: 'avoir', icon: 'undo' },
  ];

  private readonly typeOrder: { [key: string]: number } = {
    facture: 0,
    bon_livraison: 1,
    bon_commande: 2,
    devis: 3,
    avoir: 4,
  };

  sortOptions: Array<{ label: string; value: SortKey }> = [
    { label: 'Date', value: 'date' },
    { label: 'Montant', value: 'montant' },
    { label: 'Type', value: 'type' },
    { label: 'Nom', value: 'nom' },
  ];

  readonly displayedDocuments = computed(() => {
    const query = this.searchQuery().toLowerCase();
    const sort = this.sortKey();
    const asc = this.sortAsc();
    let docs = [...this.docService.filteredDocuments()];

    if (query) {
      docs = docs.filter(d =>
        d.nom_fichier.toLowerCase().includes(query) ||
        d.fournisseur_nom?.toLowerCase().includes(query) ||
        d.numero_document?.toLowerCase().includes(query),
      );
    }

    docs.sort((a, b) => {
      let cmp = 0;
      if (sort === 'date') cmp = a.created_at.localeCompare(b.created_at);
      else if (sort === 'montant') cmp = (a.montant_ttc || 0) - (b.montant_ttc || 0);
      else if (sort === 'type') cmp = (this.typeOrder[a.type_document ?? ''] ?? 99) - (this.typeOrder[b.type_document ?? ''] ?? 99);
      else if (sort === 'nom') cmp = a.nom_fichier.localeCompare(b.nom_fichier);
      return asc ? cmp : -cmp;
    });

    return docs;
  });

  constructor(
    private docService: DocumentService,
    private router: Router,
  ) {}

  setFilter(filter: DocumentType | 'all'): void {
    this.docService.setFilter(filter);
  }

  setSort(key: SortKey): void {
    if (this.sortKey() === key) {
      this.sortAsc.update(v => !v);
    } else {
      this.sortKey.set(key);
      this.sortAsc.set(false);
    }
  }

  openDocument(doc: DocumentCard): void {
    this.router.navigate(['/documents', doc.document_id]);
  }

  removeDocument(event: Event, doc: DocumentCard): void {
    event.stopPropagation();
    this.docService.removeDocument(doc.document_id);
  }

  scanNew(): void {
    this.router.navigate(['/scanner']);
  }

  getTypeColor(type?: DocumentType): string {
    return type ? this.typeColors[type] : '#9e9e9e';
  }

  getStatusIcon(status: string): string {
    const map: Record<string, string> = {
      pending: 'hourglass_empty',
      classified: 'label',
      extracted: 'check_circle',
      error: 'error',
    };
    return map[status] || 'help';
  }

  getStatusColor(status: string): string {
    const map: Record<string, string> = {
      pending: '#f57c00',
      classified: '#1976d2',
      extracted: '#388e3c',
      error: '#d32f2f',
    };
    return map[status] || '#9e9e9e';
  }
}
