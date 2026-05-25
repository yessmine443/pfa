import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { DocumentService } from '../../services/document.service';
import { ApiService } from '../../services/api.service';
import {
  DocumentCard, LigneDocument,
  DOCUMENT_TYPE_LABELS, DOCUMENT_TYPE_ICONS, DOCUMENT_TYPE_COLORS,
} from '../../models/document.model';

@Component({
  standalone: false,
  selector: 'app-document-detail',
  templateUrl: './document-detail.component.html',
  styleUrls: ['./document-detail.component.scss'],
})
export class DocumentDetailComponent implements OnInit {
  document: DocumentCard | undefined;
  documentId = '';
  exportingExcel = false;

  typeLabels: { [key: string]: string } = DOCUMENT_TYPE_LABELS;
  typeIcons:  { [key: string]: string } = DOCUMENT_TYPE_ICONS;
  typeColors: { [key: string]: string } = DOCUMENT_TYPE_COLORS;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private docService: DocumentService,
    private api: ApiService,
  ) {}

  ngOnInit(): void {
    this.documentId = this.route.snapshot.paramMap.get('id') || '';
    this.document = this.docService.documents().find(
      d => d.document_id === this.documentId
    );
  }

  back(): void { this.router.navigate(['/documents']); }

  openFile(): void {
    if (this.document?.storage_url) window.open(this.document.storage_url, '_blank');
  }

  getTypeColor(): string {
    return this.document?.type_document ? this.typeColors[this.document.type_document] : '#9e9e9e';
  }

  compareDevis(): void { this.router.navigate(['/comparer']); }

  // â”€â”€ Articles helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  get lignes(): LigneDocument[] { return this.document?.lignes || []; }

  hasRef(): boolean    { return this.lignes.some(l => l.reference); }
  hasPrixU(): boolean  { return this.lignes.some(l => l.prix_unitaire != null); }
  hasRemise(): boolean { return this.lignes.some(l => l.remise_pct != null); }
  hasTva(): boolean    { return this.lignes.some(l => l.tva_taux != null); }
  hasTtc(): boolean    { return this.lignes.some(l => (l as any).montant_ttc != null); }

  bestPrixIndex(): number {
    const prices = this.lignes.map(l => Number(l.prix_unitaire ?? 0));
    const valid = prices.filter(p => p > 0);
    if (!valid.length) return -1;
    const best = Math.min(...valid);
    return prices.findIndex(p => Math.abs(p - best) < 0.0001 && p > 0);
  }

  totalColspan(): number {
    let n = 2; // dÃ©signation + qtÃ©
    if (this.hasRef())    n++;
    if (this.hasPrixU())  n++;
    if (this.hasRemise()) n++;
    return n;
  }

  totalHT(): number {
    return this.lignes.reduce((acc, l) => acc + this.lineHt(l), 0);
  }

  private lineHt(l: any): number {
    const ht = Number(l.montant_ht);
    if (ht > 0) return ht;
    const pu = Number(l.prix_unitaire) || 0;
    const qte = Number(l.quantite) || 0;
    const rem = Number(l.remise_pct) || 0;
    if (pu > 0 && qte > 0) return pu * qte * (1 - rem / 100);
    const ttc = Number((l as any).montant_ttc) || 0;
    const tva = Number(l.tva_taux) || 0;
    if (ttc > 0) return ttc / (1 + tva / 100);
    return 0;
  }

  totalTTC(): number {
    return this.lignes.reduce((acc, l) => acc + Number((l as any).montant_ttc ?? 0), 0);
  }

  // â”€â”€ Export Excel â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  exportExcel(): void {
    if (!this.lignes.length) return;
    this.exportingExcel = true;
    this.api.exportExcel(
      this.lignes as any[],
      this.document?.nom_fichier,
      this.document?.fournisseur_nom,
    ).subscribe({
      next: (blob: Blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = (this.document?.nom_fichier || 'articles').replace(/\.[^.]+$/, '') + '_articles.xlsx';
        a.click();
        URL.revokeObjectURL(url);
        this.exportingExcel = false;
      },
      error: () => {
        alert('Erreur lors de l\'export Excel');
        this.exportingExcel = false;
      },
    });
  }
}
