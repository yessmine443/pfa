import {
  Component, ElementRef, OnDestroy, OnInit, ViewChild, signal
} from '@angular/core';
import { Router } from '@angular/router';
import { FormArray, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { DocumentService } from '../../services/document.service';
import { ApiService } from '../../services/api.service';
import {
  DOCUMENT_TYPE_LABELS, DOCUMENT_TYPE_ICONS, DOCUMENT_TYPE_COLORS, DocumentType,
  CompareResponse,
} from '../../models/document.model';

type ScanStep = 'idle' | 'camera' | 'preview' | 'processing' | 'done' | 'compare' | 'error';

export interface DevisEntry {
  nom: string;
  fournisseur: string;
  totalHt: number;
  lignes: any[];
}

@Component({
  standalone: false,
  selector: 'app-scanner',
  templateUrl: './scanner.component.html',
  styleUrls: ['./scanner.component.scss'],
})
export class ScannerComponent implements OnInit, OnDestroy {
  @ViewChild('videoEl') videoEl!: ElementRef<HTMLVideoElement>;
  @ViewChild('canvasEl') canvasEl!: ElementRef<HTMLCanvasElement>;
  @ViewChild('fileInput') fileInput!: ElementRef<HTMLInputElement>;

  step: ScanStep = 'idle';
  cameraStream: MediaStream | null = null;
  capturedFile: File | null = null;
  previewUrl: string | null = null;
  dragOver = false;

  result: any = null;
  errorMessage = '';
  compareResult = signal<CompareResponse | null>(null);
  comparing = signal(false);

  // Devis session â€” accumulates scanned devis for price comparison
  devisSession = signal<DevisEntry[]>([]);

  // Manual articles form
  articlesForm!: FormGroup;
  showManualForm = false;

  typeLabels: { [key: string]: string } = DOCUMENT_TYPE_LABELS;
  typeIcons: { [key: string]: string } = DOCUMENT_TYPE_ICONS;
  typeColors: { [key: string]: string } = DOCUMENT_TYPE_COLORS;

  readonly loading = this.docService.loading;

  constructor(
    private docService: DocumentService,
    private api: ApiService,
    private router: Router,
    private fb: FormBuilder,
  ) {
    this.articlesForm = this.fb.group({
      fournisseur_nom: ['', Validators.required],
      articles: this.fb.array([this.createArticle()]),
    });
  }

  ngOnInit(): void {}
  ngOnDestroy(): void { this.stopCamera(); }

  // ---- Articles form ----

  get articles(): FormArray {
    return this.articlesForm.get('articles') as FormArray;
  }

  createArticle(): FormGroup {
    return this.fb.group({
      designation: ['', Validators.required],
      quantite: [1, [Validators.required, Validators.min(0.001)]],
      prix_unitaire: [null, [Validators.required, Validators.min(0)]],
      unite: [''],
      reference: [''],
    });
  }

  addArticle(): void { this.articles.push(this.createArticle()); }

  removeArticle(i: number): void {
    if (this.articles.length > 1) this.articles.removeAt(i);
  }

  toggleManualForm(): void {
    this.showManualForm = !this.showManualForm;
    if (this.showManualForm && this.result?.extraction?.donnees?.fournisseur_nom) {
      this.articlesForm.patchValue({ fournisseur_nom: this.result.extraction.donnees.fournisseur_nom });
    }
  }

  saveManualArticles(): void {
    if (this.articlesForm.invalid) { this.articlesForm.markAllAsTouched(); return; }
    const { fournisseur_nom, articles } = this.articlesForm.value;
    if (!this.result) this.result = { extraction: { donnees: {} } };
    this.result.extraction.donnees.fournisseur_nom = fournisseur_nom;
    this.result.extraction.donnees.lignes = articles.map((a: any) => ({
      designation: a.designation,
      quantite: +a.quantite,
      prix_unitaire: +a.prix_unitaire,
      unite: a.unite,
      reference: a.reference,
      montant_ht: +(a.prix_unitaire * a.quantite).toFixed(2),
    }));
    this.showManualForm = false;
  }

  // ---- Camera ----

  async startCamera(): Promise<void> {
    try {
      this.cameraStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1920 } },
      });
      this.step = 'camera';
      setTimeout(() => {
        if (this.videoEl?.nativeElement && this.cameraStream) {
          this.videoEl.nativeElement.srcObject = this.cameraStream;
        }
      }, 100);
    } catch {
      this.errorMessage = "Impossible d'accÃ©der Ã  la camÃ©ra. VÃ©rifiez les permissions.";
      this.step = 'error';
    }
  }

  capture(): void {
    const video = this.videoEl?.nativeElement;
    const canvas = this.canvasEl?.nativeElement;
    if (!video || !canvas) return;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d')!.drawImage(video, 0, 0);
    canvas.toBlob(blob => {
      if (blob) {
        this.capturedFile = new File([blob], `scan_${Date.now()}.jpg`, { type: 'image/jpeg' });
        this.previewUrl = URL.createObjectURL(blob);
        this.stopCamera();
        this.step = 'preview';
      }
    }, 'image/jpeg', 0.92);
  }

  stopCamera(): void {
    this.cameraStream?.getTracks().forEach(t => t.stop());
    this.cameraStream = null;
  }

  // ---- File import ----

  openFilePicker(): void { this.fileInput?.nativeElement.click(); }

  onFileSelected(event: Event): void {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (file) this.loadFile(file);
  }

  onDragOver(e: DragEvent): void { e.preventDefault(); this.dragOver = true; }
  onDragLeave(): void { this.dragOver = false; }
  onDrop(e: DragEvent): void {
    e.preventDefault(); this.dragOver = false;
    const file = e.dataTransfer?.files[0];
    if (file) this.loadFile(file);
  }

  private loadFile(file: File): void {
    const allowed = ['application/pdf', 'image/jpeg', 'image/png', 'image/tiff'];
    if (!allowed.includes(file.type)) {
      this.errorMessage = 'Format non supportÃ©. Utilisez PDF, JPEG, PNG ou TIFF.';
      this.step = 'error';
      return;
    }
    this.capturedFile = file;
    const reader = new FileReader();
    reader.onload = e => { this.previewUrl = e.target?.result as string; };
    reader.readAsDataURL(file);
    this.step = 'preview';
  }

  // ---- Process ----

  processDocument(): void {
    if (!this.capturedFile) return;
    this.step = 'processing';
    this.docService.processFile(this.capturedFile).subscribe({
      next: (result: any) => {
        this.result = result;
        this.showManualForm = false;
        if (result?.extraction?.donnees?.fournisseur_nom) {
          this.articlesForm.patchValue({ fournisseur_nom: result.extraction.donnees.fournisseur_nom });
        }
        // Auto-add to devis session if document is a devis
        if (result?.classification?.type_document === 'devis') {
          this._addToDevisSession(result);
        }
        this.step = 'done';
      },
      error: (err: Error) => {
        this.errorMessage = err.message;
        this.step = 'error';
      },
    });
  }

  private _addToDevisSession(result: any): void {
    const lignes = result?.extraction?.donnees?.lignes || [];
    const totalHt = lignes.reduce((s: number, l: any) => s + (Number(l.montant_ht) || 0), 0);
    const fournisseur = result?.extraction?.donnees?.fournisseur_nom
      || this.capturedFile?.name?.replace(/\.[^.]+$/, '')
      || 'Fournisseur';
    const entry: DevisEntry = {
      nom: this.capturedFile?.name || 'devis',
      fournisseur,
      totalHt,
      lignes,
    };
    // Replace existing entry if same fournisseur, otherwise append
    const current = this.devisSession();
    const idx = current.findIndex(d => d.fournisseur === fournisseur);
    if (idx >= 0) {
      const updated = [...current];
      updated[idx] = entry;
      this.devisSession.set(updated);
    } else {
      this.devisSession.set([...current, entry]);
    }
  }

  // ---- Devis session comparison ----

  get meilleureOffre(): DevisEntry | null {
    const s = this.devisSession();
    if (s.length < 2) return null;
    return s.reduce((best, d) => d.totalHt < best.totalHt ? d : best);
  }

  get devisSessionSorted(): DevisEntry[] {
    return [...this.devisSession()].sort((a, b) => a.totalHt - b.totalHt);
  }

  economieVsMeilleur(entry: DevisEntry): number {
    const best = this.meilleureOffre;
    if (!best) return 0;
    return entry.totalHt - best.totalHt;
  }

  removeFromSession(idx: number): void {
    const updated = [...this.devisSession()];
    updated.splice(idx, 1);
    this.devisSession.set(updated);
  }

  clearSession(): void { this.devisSession.set([]); }

  // ---- Compare prices ----

  get lignes(): any[] {
    return this.result?.extraction?.donnees?.lignes || [];
  }

  get hasLignes(): boolean { return this.lignes.length > 0; }

  get isDevis(): boolean {
    return this.result?.classification?.type_document === 'devis';
  }

  goToCompare(): void {
    this.step = 'compare';
    this.compareResult.set(null);
  }

  compareWithOthers(referenceIndex: number): void {
    const ligne = this.lignes[referenceIndex];
    if (!ligne) return;

    const fournisseur = this.result?.extraction?.donnees?.fournisseur_nom || 'Fournisseur actuel';
    const prixActuel = ligne.prix_unitaire || (ligne.montant_ht / (ligne.quantite || 1));

    this.comparing.set(true);
    this.api.comparePrices({
      reference_produit: ligne.reference || ligne.designation,
      designation: ligne.designation,
      items: [{
        devis_id: this.result?.upload?.document_id || 'current',
        fournisseur_nom: fournisseur,
        prix_unitaire: prixActuel,
        quantite: ligne.quantite || 1,
      }],
    }).subscribe({
      next: res => { this.compareResult.set(res); this.comparing.set(false); },
      error: () => { this.comparing.set(false); },
    });
  }

  navigateToComparateur(): void {
    this.router.navigate(['/comparer']);
  }

  // ---- Actions ----

  reset(): void {
    this.step = 'idle';
    this.capturedFile = null;
    this.previewUrl = null;
    this.result = null;
    this.errorMessage = '';
    this.showManualForm = false;
    this.compareResult.set(null);
    this.articlesForm.reset();
    while (this.articles.length > 1) this.articles.removeAt(1);
    this.stopCamera();
  }

  goToDocuments(): void { this.router.navigate(['/documents']); }

  exportingExcel = false;

  exportExcel(): void {
    if (!this.hasLignes || this.exportingExcel) return;
    this.exportingExcel = true;
    const nom = this.capturedFile?.name?.replace(/\.[^.]+$/, '') || 'export';
    const fournisseur = this.result?.extraction?.donnees?.fournisseur_nom;
    this.api.exportExcel(this.lignes, nom, fournisseur).subscribe({
      next: (blob: Blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${nom}_articles.xlsx`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        this.exportingExcel = false;
      },
      error: (err: Error) => {
        this.exportingExcel = false;
        alert('Erreur export Excel : ' + (err.message || 'VÃ©rifiez que le backend est lancÃ©'));
      },
    });
  }

  getTypeIcon(type: string): string { return this.typeIcons[type] || 'description'; }
  getTypeLabel(type: string): string { return this.typeLabels[type] || type; }
  getDocTypeColor(type: string): string { return this.typeColors[type] || '#666'; }

  get confidencePercent(): number {
    return Math.round((this.result?.classification?.score_confiance || 0) * 100);
  }

  get totalLignes(): number {
    return this.lignes.reduce((s: number, l: any) => s + this.lineHt(l), 0);
  }

  private lineHt(l: any): number {
    const ht = Number(l.montant_ht);
    if (ht > 0) return ht;
    const pu = Number(l.prix_unitaire) || 0;
    const qte = Number(l.quantite) || 0;
    const rem = Number(l.remise_pct) || 0;
    if (pu > 0 && qte > 0) return pu * qte * (1 - rem / 100);
    const ttc = Number(l.montant_ttc) || 0;
    const tva = Number(l.tva_taux) || 0;
    if (ttc > 0) return ttc / (1 + tva / 100);
    return 0;
  }

  // Index of the ligne with lowest prix_unitaire (for green highlight)
  get bestPrixIndex(): number {
    if (!this.hasLignes) return -1;
    let bestIdx = -1, bestVal = Infinity;
    this.lignes.forEach((l: any, i: number) => {
      const v = Number(l.prix_unitaire) || 0;
      if (v > 0 && v < bestVal) { bestVal = v; bestIdx = i; }
    });
    return bestIdx;
  }

  // Dynamic column visibility based on extracted data
  get hasRef(): boolean { return this.lignes.some((l: any) => l.reference); }
  get hasPrixU(): boolean { return this.lignes.some((l: any) => l.prix_unitaire != null); }
  get hasRemise(): boolean { return this.lignes.some((l: any) => l.remise_pct != null); }
  get hasTva(): boolean { return this.lignes.some((l: any) => l.tva_taux != null); }
  get hasMontantTtc(): boolean { return this.lignes.some((l: any) => l.montant_ttc != null); }

  get totalColspan(): number {
    let n = 2; // DÃ©signation + QtÃ© always
    if (this.hasRef) n++;
    if (this.hasPrixU) n++;
    if (this.hasRemise) n++;
    if (this.hasTva) n++;
    return n;
  }
}
