import { Component, OnInit, computed } from '@angular/core';
import { Router, NavigationEnd } from '@angular/router';
import { ApiService } from './services/api.service';
import { DocumentService } from './services/document.service';
import { filter } from 'rxjs/operators';

@Component({
  standalone: false,
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss'],
})
export class AppComponent implements OnInit {
  title = 'SPARKY';
  apiOnline = false;
  sidenavOpened = false;
  isLoginPage = false;

  navItems = [
    { label: 'Tableau de bord',      icon: 'dashboard',        route: '/home' },
    { label: 'Scanner',              icon: 'document_scanner', route: '/scanner' },
    { label: 'Documents',            icon: 'folder_open',      route: '/documents' },
    { label: 'Comparateur des prix', icon: 'compare_arrows',   route: '/comparer' },
  ];

  readonly totaux = computed(() => {
    const docs = this.docService.documents();
    const sum = (type: string) => docs
      .filter(d => d.type_document === type && d.montant_ttc)
      .reduce((acc, d) => acc + Number(d.montant_ttc), 0);
    return {
      factures: sum('facture'),
      devis:    sum('devis'),
      commandes: sum('bon_commande'),
    };
  });

  constructor(
    private api: ApiService,
    private docService: DocumentService,
    private router: Router,
  ) {}

  ngOnInit(): void {
    this.api.health().subscribe({
      next: () => (this.apiOnline = true),
      error: () => (this.apiOnline = false),
    });

    this.router.events.pipe(
      filter(e => e instanceof NavigationEnd)
    ).subscribe((e: any) => {
      this.isLoginPage = e.urlAfterRedirects.startsWith('/login');
    });
  }

  toggleSidenav(): void {
    this.sidenavOpened = !this.sidenavOpened;
  }

  logout(): void {
    this.router.navigate(['/login']);
  }
}
