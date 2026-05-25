import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { DocumentService } from '../../services/document.service';
import { DOCUMENT_TYPE_LABELS, DOCUMENT_TYPE_ICONS, DOCUMENT_TYPE_COLORS } from '../../models/document.model';

@Component({
  standalone: false,
  selector: 'app-home',
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.scss'],
})
export class HomeComponent {
  readonly stats = this.docService.stats;
  readonly recentDocs = this.docService.filteredDocuments;

  typeLabels: { [key: string]: string } = DOCUMENT_TYPE_LABELS;
  typeIcons: { [key: string]: string } = DOCUMENT_TYPE_ICONS;
  typeColors: { [key: string]: string } = DOCUMENT_TYPE_COLORS;

  statCards = [
    {
      label: 'Total Documents',
      key: 'total' as const,
      icon: 'folder_open',
      color: '#1976d2',
      route: '/documents',
    },
    {
      label: 'Factures',
      key: 'factures' as const,
      icon: 'receipt',
      color: '#1976d2',
      route: '/documents',
      filter: 'facture',
    },
    {
      label: 'Bons de Livraison',
      key: 'bons_livraison' as const,
      icon: 'local_shipping',
      color: '#388e3c',
      route: '/documents',
      filter: 'bon_livraison',
    },
    {
      label: 'Bons de Commande',
      key: 'bons_commande' as const,
      icon: 'shopping_cart',
      color: '#f57c00',
      route: '/documents',
      filter: 'bon_commande',
    },
    {
      label: 'Devis',
      key: 'devis' as const,
      icon: 'request_quote',
      color: '#7b1fa2',
      route: '/documents',
      filter: 'devis',
    },
    {
      label: 'Avoirs',
      key: 'avoirs' as const,
      icon: 'undo',
      color: '#d32f2f',
      route: '/documents',
      filter: 'avoir',
    },
  ];

  quickActions = [
    {
      label: 'Scanner un document',
      icon: 'document_scanner',
      route: '/scanner',
      color: '#f5c518',
      description: 'Utilisez la camÃ©ra ou importez un fichier',
    },
    {
      label: 'Comparateur des prix',
      icon: 'compare_arrows',
      route: '/comparer',
      color: '#7b1fa2',
      description: 'Trouvez le meilleur prix fournisseur',
    },
    {
      label: 'Voir les documents',
      icon: 'folder_open',
      route: '/documents',
      color: '#1976d2',
      description: 'Parcourez tous vos documents',
    },
  ];

  constructor(
    private router: Router,
    private docService: DocumentService,
  ) {}

  navigate(route: string, filter?: string): void {
    if (filter) {
      this.docService.setFilter(filter as any);
    }
    this.router.navigate([route]);
  }
}
