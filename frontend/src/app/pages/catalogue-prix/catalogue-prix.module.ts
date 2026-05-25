import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatTableModule } from '@angular/material/table';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { CataloguePrixComponent } from './catalogue-prix.component';
import { BackButtonComponent } from '../../components/back-button/back-button.component';

@NgModule({
  declarations: [CataloguePrixComponent],
  imports: [
    CommonModule,
    RouterModule.forChild([{ path: '', component: CataloguePrixComponent }]),
    MatCardModule,
    MatIconModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatTableModule,
    MatProgressBarModule,
    MatTooltipModule,
    BackButtonComponent,
  ],
})
export class CataloguePrixModule {}
