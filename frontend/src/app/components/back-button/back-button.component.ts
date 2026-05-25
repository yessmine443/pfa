import { Component } from '@angular/core';
import { Location } from '@angular/common';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatTooltipModule } from '@angular/material/tooltip';

@Component({
  standalone: true,
  selector: 'app-back-button',
  imports: [MatIconModule, MatButtonModule, MatTooltipModule],
  template: `
    <button
      mat-icon-button
      class="back-btn"
      (click)="goBack()"
      matTooltip="Retour"
      aria-label="Retour">
      <mat-icon>arrow_back</mat-icon>
    </button>
  `,
  styles: [`
    .back-btn {
      color: #1a1a2e;
      background: #fff;
      border: 1.5px solid #e0e0e0;
      margin-right: 12px;
      transition: all .15s ease;
    }
    .back-btn:hover {
      background: #f5c518;
      border-color: #f5c518;
      transform: translateX(-2px);
    }
  `],
})
export class BackButtonComponent {
  constructor(private location: Location) {}
  goBack(): void { this.location.back(); }
}
