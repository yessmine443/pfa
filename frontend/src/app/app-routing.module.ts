import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

const routes: Routes = [
  {
    path: '',
    redirectTo: 'login',
    pathMatch: 'full',
  },
  {
    path: 'login',
    loadChildren: () =>
      import('./pages/login/login.module').then(m => m.LoginModule),
  },
  {
    path: 'home',
    loadChildren: () =>
      import('./pages/home/home.module').then(m => m.HomeModule),
  },
  {
    path: 'scanner',
    loadChildren: () =>
      import('./pages/scanner/scanner.module').then(m => m.ScannerModule),
  },
  {
    path: 'documents',
    loadChildren: () =>
      import('./pages/documents/documents.module').then(m => m.DocumentsModule),
  },
  {
    path: 'documents/:id',
    loadChildren: () =>
      import('./pages/document-detail/document-detail.module').then(
        m => m.DocumentDetailModule
      ),
  },
  {
    path: 'comparer',
    loadChildren: () =>
      import('./pages/price-comparison/price-comparison.module').then(
        m => m.PriceComparisonModule
      ),
  },
  {
    path: 'catalogue-prix',
    loadChildren: () =>
      import('./pages/catalogue-prix/catalogue-prix.module').then(
        m => m.CataloguePrixModule
      ),
  },
  {
    path: '**',
    redirectTo: 'home',
  },
];

@NgModule({
  imports: [RouterModule.forRoot(routes, { scrollPositionRestoration: 'top', onSameUrlNavigation: 'reload' })],
  exports: [RouterModule],
})
export class AppRoutingModule {}
