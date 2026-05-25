import { Component, EventEmitter, Output } from '@angular/core';
import { Router } from '@angular/router';

@Component({
  standalone: false,
  selector: 'app-navbar',
  templateUrl: './navbar.component.html',
  styleUrls: ['./navbar.component.scss'],
})
export class NavbarComponent {
  @Output() toggleSidenav = new EventEmitter<void>();

  constructor(private router: Router) {}

  onScanClick(): void {
    this.router.navigate(['/scanner']);
  }
}
