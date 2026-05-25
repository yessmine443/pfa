import { Component, OnInit, OnDestroy } from '@angular/core';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { ApiService } from '../../services/api.service';
import {
  ComparaisonPrixResponse,
  ArticlePrixComparaison,
  PrixFournisseur,
} from '../../models/document.model';

@Component({
  standalone: false,
  selector: 'app-catalogue-prix',
  templateUrl: './catalogue-prix.component.html',
  styleUrls: ['./catalogue-prix.component.scss'],
})
export class CataloguePrixComponent implements OnInit, OnDestroy {
  private destroy$ = new Subject<void>();

  loading    = false;
  error: string | null = null;
  data: ComparaisonPrixResponse | null = null;

  searchText    = '';
  filterCategorie = '';

  // derived â€“ rebuilt whenever data/filters change
  categories: string[]                 = [];
  filteredArticles: ArticlePrixComparaison[] = [];
  displayedColumns: string[]           = [];

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.load();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  load(categorie?: string): void {
    this.loading = true;
    this.error   = null;

    this.api.getComparaisonPrix(categorie)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: res => {
          this.data    = res;
          this.loading = false;
          this._buildDerived();
        },
        error: err => {
          this.error   = err.message;
          this.loading = false;
        },
      });
  }

  onSearch(value: string): void {
    this.searchText = value;
    this._applyFilters();
  }

  onCategorie(value: string): void {
    this.filterCategorie = value;
    this._applyFilters();
  }

  // Return the PrixFournisseur entry for a given supplier name, or null
  getPrixFourn(article: ArticlePrixComparaison, fournisseurNom: string): PrixFournisseur | null {
    return article.prix_par_fournisseur.find(p => p.fournisseur_nom === fournisseurNom) ?? null;
  }

  // CSS class for the gap badge
  gapClass(pct: number | undefined): string {
    if (!pct || pct === 0) return '';
    if (pct < 10)  return 'gap-low';
    if (pct < 30)  return 'gap-mid';
    return 'gap-high';
  }

  exportCsv(): void {
    if (!this.data) return;
    const fournisseurs = this.data.fournisseurs;
    const header = [
      'RÃ©fÃ©rence', 'Article', 'CatÃ©gorie', 'Stock', 'UnitÃ©',
      'Meilleur prix (TND)', 'Meilleur fournisseur', 'Ã‰cart max %',
      ...fournisseurs.map(f => `${f} â€” prix achat`),
      ...fournisseurs.map(f => `${f} â€” surcoÃ»t %`),
    ].join(';');

    const rows = this.filteredArticles.map(a => {
      const base = [
        a.reference_interne,
        `"${a.nom_normalise}"`,
        a.categorie ?? '',
        a.quantite_stock,
        a.unite_mesure ?? '',
        a.meilleur_prix_achat ?? '',
        a.meilleur_fournisseur ?? '',
        a.economie_max_pct ?? 0,
      ];
      const prix    = fournisseurs.map(f => this.getPrixFourn(a, f)?.prix_achat   ?? '');
      const surcout = fournisseurs.map(f => this.getPrixFourn(a, f)?.surcout_pct  ?? '');
      return [...base, ...prix, ...surcout].join(';');
    });

    const csv  = [header, ...rows].join('\n');
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url;
    a.download = 'comparaison_prix.csv';
    a.click();
    URL.revokeObjectURL(url);
  }

  // â”€â”€ private helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  private _buildDerived(): void {
    if (!this.data) return;

    // categories list
    this.categories = [...new Set(
      this.data.articles
        .map(a => a.categorie)
        .filter((c): c is string => !!c)
    )].sort();

    // column list: fixed + one per supplier
    this.displayedColumns = [
      'article', 'categorie', 'stock',
      'best_prix', 'best_fourn', 'ecart',
      ...this.data.fournisseurs.map(f => 'f__' + this._slug(f)),
    ];

    this._applyFilters();
  }

  private _applyFilters(): void {
    if (!this.data) return;
    const q   = this.searchText.toLowerCase().trim();
    const cat = this.filterCategorie;

    this.filteredArticles = this.data.articles.filter(a => {
      const matchCat  = !cat || a.categorie === cat;
      const matchText = !q
        || a.nom_normalise.toLowerCase().includes(q)
        || a.reference_interne.toLowerCase().includes(q);
      return matchCat && matchText;
    });
  }

  _slug(s: string): string {
    return s.replace(/[^a-zA-Z0-9]/g, '_');
  }
}
