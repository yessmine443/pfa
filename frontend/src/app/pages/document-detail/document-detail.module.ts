import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatChipsModule } from '@angular/material/chips';
import { MatDividerModule } from '@angular/material/divider';
import { MatTableModule } from '@angular/material/table';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { DocumentDetailComponent } from './document-detail.component';
import { BackButtonComponent } from '../../components/back-button/back-button.component';

@NgModule({
  declarations: [DocumentDetailComponent],
  imports: [
    CommonModule,
    RouterModule.forChild([{ path: '', component: DocumentDetailComponent }]),
    MatCardModule,
    MatIconModule,
    MatButtonModule,
    MatChipsModule,
    MatDividerModule,
    MatTableModule,
    MatProgressBarModule,
    MatTooltipModule,
    BackButtonComponent,
  ],
})
export class DocumentDetailModule {}
