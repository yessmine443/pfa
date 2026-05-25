import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { PriceComparisonComponent } from './price-comparison.component';
import { BackButtonComponent } from '../../components/back-button/back-button.component';

@NgModule({
  declarations: [PriceComparisonComponent],
  imports: [
    CommonModule,
    RouterModule.forChild([{ path: '', component: PriceComparisonComponent }]),
    MatCardModule,
    MatIconModule,
    MatButtonModule,
    MatProgressBarModule,
    MatTooltipModule,
    BackButtonComponent,
  ],
})
export class PriceComparisonModule {}
