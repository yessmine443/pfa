import { Component, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { ApiService } from '../../services/api.service';

@Component({
  standalone: false,
  selector: 'app-login',
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.scss'],
})
export class LoginComponent implements OnInit {
  // Splash
  splashVisible = true;
  splashFading  = false;

  // Login
  form!: FormGroup;
  loading  = signal(false);
  showPass = signal(false);
  error    = signal<string | null>(null);

  constructor(private fb: FormBuilder, private router: Router, private api: ApiService) {}

  ngOnInit(): void {
    this.form = this.fb.group({
      email:    ['', [Validators.required, Validators.email]],
      password: ['', [Validators.required, Validators.minLength(4)]],
    });

    // Splash: 2.5s display then fade out
    setTimeout(() => {
      this.splashFading = true;
      setTimeout(() => { this.splashVisible = false; }, 600);
    }, 2500);
  }

  login(): void {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    this.loading.set(true);
    this.error.set(null);

    const { email, password } = this.form.value;
    this.api.login(email, password).subscribe({
      next: (user) => {
        localStorage.setItem('sparky_user', JSON.stringify(user));
        this.loading.set(false);
        this.router.navigate(['/home']);
      },
      error: (err) => {
        this.error.set(err.message || 'Email ou mot de passe incorrect.');
        this.loading.set(false);
      },
    });
  }

  togglePass(): void { this.showPass.update(v => !v); }
}
