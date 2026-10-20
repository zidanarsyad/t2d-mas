# Report revisions for the report's source file

*Date: 20 October 2026.* The final report, `docs/Laporan_Proyek1_T2D-MAS_Final.pdf`, is exported
from `Laporan_Proyek1_T2D-MAS_Final.docx`. That is a Word file kept in the group's Google Drive and
edited in Google Docs, not a native Google Doc. This sheet lists every passage that no longer
matches the code, with Indonesian text ready to paste. Apply the edits to that file, export the PDF
again, and replace the file in `docs/`.

- **Part 1 is required.** On 20 October six numbers were patched directly into the PDF. If they are
  not also changed in the source file, the next export brings the old numbers back.
- **Part 2** updates the passages that describe the implementation. Design passages (worked
  examples, the flash-sale timeline in Tabel 37, the specifications in Lampiran B) stay as they are;
  where the code differs, a short note is added instead.
- **Table and figure numbers do not change** if you follow this sheet. The new screen mapping in
  §8.3 is a list, not a table, so Tabel 36–47 keep their numbers (other documents cite Tabel 40
  and 41).
- `docs/Laporan - Proyek 1 - MAS - T2D.docx` is a mid-September draft with `[ISI]` placeholders.
  It is not the source of the PDF and was not revised.

The reasons behind each change are in [AUDIT.md](AUDIT.md).

**Status (20 October 2026):** every edit below is applied as a tracked change (author "Claude") in a
local copy of the .docx (`docs/Laporan_Proyek1_T2D-MAS_Final.docx`, deliberately not committed). That
copy was built on the Drive file's revision of
20 October, 10:33 UTC, including the cover-page change made that day. It still has to be uploaded as
a new version of the Drive file. Part 3's figure is marked with a comment on the Gambar 3 caption.

## Part 1: numbers already patched in the PDF

Use Find and replace in Google Docs. Each text appears once.

| Where | Find | Replace with |
|---|---|---|
| §9.4, first paragraph | `29 September 2026` | `30 September 2026` |
| Tabel 40, wall time, A0 | `0,090 ms` | `0,102 ms` |
| Tabel 40, wall time, A1 | `0,121 ms` | `0,155 ms` |
| Tabel 40, wall time, A2 | `0,145 ms` | `0,184 ms` |
| Tabel 40, wall time, A3 | `0,176 ms` | `0,198 ms` |
| §9.5, "Hasil yang dijalankan" | `p = 0,0018` | `p = 0,0136` |

These are the values of `results/20260930T020846305626`, the run the report and the deck cite.

## Part 2: passages that describe the implementation

### 1. Abstrak, first paragraph, last sentence

**Now:** "…sepanjang sembilan tahap alur kerja sambil mempertahankan tiga gerbang persetujuan manusia."

**Replace with:**

> …sepanjang sembilan tahap alur kerja sambil mempertahankan kendali manusia melalui enam jenis
> gerbang. Penggabungan PR dan rilis penuh selalu menunggu persetujuan manusia, sedangkan empat
> gerbang lainnya hanya berhenti ketika aturannya terpicu.

### 2. §4.4 Ruang Lingkup dan Batasan

**Now:** "…empat kelas agen dengan sembilan instansiasi…" and "…yang diganti dengan API tiruan (mock) dan dataset publik…"

**Replace with:** "…empat kelas agen dengan sebelas instansiasi…" and "…yang diganti dengan simulator berbenih dan dataset publik…"

Eleven matches Tabel 14 and the code: three Scouts, two Brokers, five Workers and Security-Policy. This
also settles item 4 of Tabel 46 (see item 19).

### 3. §5.5, the paragraph after Gambar 1

**Now:** "Tiga gerbang persetujuan manusia dipertahankan dari desain sebelumnya…" and the list of three gates.

**Replace with:**

> Tiga gerbang persetujuan manusia dari desain sebelumnya ditandai merah pada diagram. Purwarupa
> mewujudkan ketiganya dan menambahkan tiga gerbang bersyarat, sehingga terdapat enam jenis
> gerbang berikut.
> 1. Tinjauan duplikat (duplicate_review): berhenti bila kemiripan kosinus dengan tiket sebelumnya
>    berada pada rentang 0,70 sampai 0,85.
> 2. Gerbang otonomi (autonomy_gate) setelah Broker-Triage: berhenti bila P < τ (0,70) atau
>    risiko > R_maks (0,60). Pada gerbang ini manusia dapat mengoreksi severity.
> 3. Pemindaian rahasia (secret_scan) setelah Worker-Impl: berhenti bila draf perubahan memuat
>    rahasia. Draf hanya dapat ditulis ulang atau dihentikan, tidak dapat disetujui.
> 4. Tinjauan kode dan penggabungan PR (pr_merge) setelah Worker-QA: selalu berhenti.
> 5. Tinjauan canary (canary_review): berhenti bila skor risiko rilis lebih dari 0,30.
> 6. Persetujuan rilis penuh (release_signoff) sebelum Worker-Deploy merilis ke seluruh pengguna:
>    selalu berhenti.
>
> Penggabungan dan rilis penuh hanya dijalankan melalui execute_irreversible(), yang memeriksa
> persetujuan yang tercatat, dan dijaga sekali lagi oleh trigger basis data.

### 4. §5.6.2 Skema Pesan

**Add after** "…konteks kebijakan, dan tanda tangan digital.":

> Pada purwarupa, bidang signature disediakan tetapi dibiarkan kosong; yang ditandatangani dengan
> Ed25519 adalah paket agen bergerak. Bidang tersebut tetap dipertahankan karena jumlah byte pada
> percobaan Bab 9 ikut menghitungnya.

### 5. §6.4.1, after "…sebesar 450 jam pada Subbab 2.3."

**Add a paragraph:**

> Pada purwarupa, Broker-Triage menghitung kemiripan dengan TF-IDF atas n-gram karakter (3 sampai 5)
> dan kemiripan kosinus terhadap tiket yang masuk lebih dahulu, dengan tiga zona yang sama: nilai
> ≥ 0,85 ditautkan otomatis dan tiket ditutup sebagai duplikat, nilai 0,70 sampai 0,85 menunggu
> keputusan manusia, dan nilai < 0,70 menjadi tiket baru. Implementasi ini mereproduksi contoh di
> atas (0,994 dan 0,119). Model SBERT (all-MiniLM-L6-v2) dengan indeks FAISS tersedia pada modul
> luring triage/, tetapi belum dipakai pada alur langsung. Karena bersifat leksikal, pencarian ini
> belum dapat mencocokkan laporan berbahasa Indonesia dengan laporan berbahasa Inggris tentang
> masalah yang sama.

### 6. §7.1 Basis Data Operasional and Tabel 28

**Now:** "Rancangan terdiri atas dua belas tabel, yang tersaji pada Tabel 28…"

**Replace with:**

> Rancangan awal terdiri atas dua belas tabel. Purwarupa hanya mempertahankan enam tabel yang
> benar-benar ditulis atau dibaca oleh agen, yang tersaji pada Tabel 28, dan hubungan antartabel
> digambarkan pada Gambar 3.

**Replace the rows of Tabel 28 with:**

| Tabel | Kolom kunci | Fungsi |
|---|---|---|
| tickets | ticket_id, source, title, body, component, severity, status, language, app_version, platform, duplicate_of, parent_ticket_id, dataset_version | Entitas utama tiket, termasuk tautan duplikat dan tiket lanjutan dari pemantauan |
| code_changes | change_id, ticket_id, repository, branch_name, diff_summary, files, tests_added, merged, human_approved, approved_by | Draf PR dari Worker-Impl; trigger menolak merged tanpa human_approved |
| deployments | deployment_id, change_id, ticket_id, environment (canary/production), strategy, risk_score, status, human_approved, slo_breach, rollback_of | Canary dan rilis dari Worker-Deploy; trigger menolak status deployed tanpa human_approved |
| policies | policy_id, name, tau, risk_max, rules (jsonb), version, active, approved_by | Kebijakan tata kelola berversi; diisi dari agents/policy.py saat orkestrator mulai |
| audit_log | audit_id, occurred_at, correlation_id, actor_id, action, ticket_id, decision, human_approved, details (jsonb) | Jejak audit append-only: keluaran agen, hasil gerbang, pesan, persetujuan, dan aksi yang diblokir |
| slo_baselines | service, metric, window_minutes, baseline_mean, baseline_std, slo_threshold, unit | Garis dasar bagi Scout-Monitor; diisi dari simulator saat orkestrator mulai |

**Add after the table:**

> Tabel ticket_embeddings, agents, messages, evidence, tasks, dan test_runs dihapus karena tidak
> dipakai. Pesan antaragen dan bukti teragregasi dicatat di audit_log, dan ekstensi pgvector tidak
> digunakan.

**In the next paragraph, change** "…menolak setiap perintah UPDATE dan DELETE terhadap tabel tersebut." **to** "…menolak setiap perintah UPDATE, DELETE, dan TRUNCATE terhadap tabel tersebut."

### 7. §7.4 Integrasi API Perusahaan (Simulasi) and Tabel 32

**Now:** "Karena akses ke sistem berbayar tidak tersedia, integrasi disimulasikan melalui layanan tiruan (mock service)…" up to "…Pemetaannya tersaji pada Tabel 32."

**Replace with:**

> Karena akses ke sistem berbayar tidak tersedia, integrasi disimulasikan dengan simulator yang
> berjalan di dalam proses orkestrator (agents/tools.py) dan meniru bentuk respons sistem nyata.
> Setiap simulator diberi benih dari ID tiket sehingga hasilnya dapat direproduksi, dan setiap
> keluaran agen diberi label simulated atau mixed. Layanan FastAPI tiruan pada rancangan awal
> (data/mock_api) dihapus karena tidak dipakai. Pemetaannya tersaji pada Tabel 32.

**Replace Tabel 32 (title: "Simulator dan sistem nyata yang ditiru") with:**

| Sistem nyata | Simulator (agents/tools.py) | Dipakai oleh |
|---|---|---|
| Jira atau papan proyek | project_board: kapasitas sprint dan estimasi | Worker-Plan |
| GitHub | repository_context, draft_diff: konteks layanan dan draf PR | Worker-Impl |
| Datadog atau observabilitas | node_logs, telemetry: log per simpul dan metrik layanan | Scout-Log, Scout-Monitor |
| CI/CD | test_catalog, run_ci: katalog 3.400 tes dan hasil CI | Worker-QA |
| Infrastruktur dan deploy | run_canary, deployment_history, post_release_metrics | Worker-Deploy, Scout-Monitor |

### 8. §8.1 Lingkup Purwarupa and Tabel 34

**Now:** "…sehingga berbeda dari rancangan awal pada satu hal penting, yaitu model bahasa besar belum terhubung."

**Replace with:**

> …Perbedaan terpenting dari rancangan awal adalah bahwa sistem nyata (repositori, CI, klaster, dan
> telemetri) digantikan oleh simulator berbenih, dan model bahasa besar hanya terhubung secara
> opsional.

**Replace the status column of Tabel 34:**

| Komponen | Status pada purwarupa |
|---|---|
| Empat arketipe agen (11 instansiasi) | Diimplementasikan sebagai kelas Python di dalam orkestrator FastAPI dengan siklus lima komponen (perceive, remember, reason, act, report). Pesan antaragen melalui Redis Streams pada mode Docker, atau bus di memori pada mode lokal tanpa Docker |
| Mobilitas agen | Scout-Log mengunjungi enam simpul pada tahap investigasi. Aturan L_node > (A + R) × 3 (ambang 42 MB) diterapkan per simpul: lima simpul menjalankan paket bertanda tangan Ed25519 di samping log lokalnya, sedangkan simpul-6 (30 MB) menjawab melalui eksportirnya. Hanya bidang agregat dalam daftar izin yang kembali. Simpul berupa kontainer Docker, atau berjalan di dalam proses pada mode lokal |
| Model bahasa besar (LLM) | Opsional. Bila OPENROUTER_API_KEY diisi, Broker-Triage dan penafsiran catatan peninjau memakai model gratis OpenRouter (hanya ID berakhiran :free); keyakinan model dibatasi di bawah τ sehingga manusia tetap meninjau. Tanpa kunci, dipakai aturan lokal berbahasa Inggris dan Indonesia. Harness evaluasi tidak memanggil LLM |
| Dataset | Pemuat data publik tersedia, tetapi percobaan yang dilaporkan memakai tiket sintetis (Subbab 7.3). Demo memakai 42 pesan umpan balik tiruan berbahasa Indonesia dan Inggris dari enam kanal |
| Deployment nyata | Tidak ada. Canary, rilis, dan rollback disimulasikan, tetapi aturan gerbang dan pencatatannya nyata |
| Alur menyeluruh | Berjalan dari umpan balik sampai pemantauan melalui sembilan agen dan berhenti pada gerbang manusia. Perencanaan, implementasi, QA, deployment, dan pemantauan memakai simulator berbenih. Model terlatih pada triage/, rca/, dan envs/ tetap luring; alur langsung memakai padanan yang lebih sederhana (TF-IDF, perhitungan acuan GraphSAGE-mean, dan aturan tetap) |

### 9. §8.2 Tumpukan Teknologi, Tabel 35

Change these rows; the others stay.

| Lapisan | Pilihan | Alasan |
|---|---|---|
| Orkestrasi agen | Mesin keadaan buatan sendiri (agents/orchestrator.py) | Kendali eksplisit atas transisi dan gerbang |
| Message bus | Redis Streams; bus di memori pada mode lokal | Ringan; panjang aliran dibatasi dan dasbor dapat memutar ulang percakapan |
| Model teks | sentence-transformers dan HuggingFace Transformers (modul luring triage/); TF-IDF n-gram karakter pada alur langsung | Sesuai Subbab 6.4 |
| Basis data | PostgreSQL (enam tabel); penyimpanan di memori pada mode lokal; FAISS pada modul luring | Sesuai Bab 7 |
| Frontend | React 19, Vite 7, Recharts, dan CSS biasa | Dasbor interaktif; Tailwind dihapus karena hanya terpakai sebagai reset CSS |
| Kontainer | Docker Compose (opsional) | Menyimulasikan banyak simpul bagi agen bergerak; mode lokal berjalan tanpa Docker |

### 10. §8.3 Rancangan UI/UX

**Now:** "…Kerangka kelima layar tersaji pada Gambar 4, dan penjelasan setiap layar diuraikan setelahnya."

**Replace with:**

> …Kerangka kelima layar tersaji pada Gambar 4, dan penjelasan setiap layar diuraikan setelahnya.
> Dasbor yang dibangun mempertahankan prinsip tersebut dengan delapan tampilan. Setiap tampilan
> dibuka dengan satu kalimat tentang apa yang terlihat dan mengapa hal itu penting. Pemetaan layar
> rancangan ke tampilan dasbor adalah sebagai berikut.
> - Layar 1 (Pipeline Overview) menjadi tampilan Tickets, tab Board: papan sembilan kolom dengan
>   ID, severity berwarna dan berlabel, agen pemegang, waktu di tahap, dan lencana "Waiting for a
>   human".
> - Layar 2 (Agent Status) menjadi tampilan Agents: keluarga agen, statis atau bergerak, beban dan
>   tiket yang sedang ditangani, lima komponen, serta tombol "Investigate on the real nodes" yang
>   menganimasikan jalur migrasi Scout-Log beserta penghitung byte.
> - Layar 3 (Decision Trace) menjadi tampilan Decision trace: alur animasi yang dapat digeser dan
>   linimasa setiap keputusan (nilai terhadap τ dan R_maks, hasil gerbang, dan penyetuju), dengan
>   ekspor JSON.
> - Layar 4 (Approval Inbox) menjadi tampilan Human reviews: antrean terurut risiko × waktu tunggu,
>   bukti berupa nilai terhadap batasnya, dan tabel enam gerbang.
> - Layar 5 (Performance Report) menjadi tampilan Monitoring: pemutaran telemetri dengan garis SLO,
>   alarm yang menjadi tiket lanjutan, batang canary, serta laporan DORA ilustratif dengan sakelar
>   Static/Mobile dan ekspor CSV.
> - Tiga tampilan tambahan: Overview (pemutaran ulang skenario TCK-1042), Run a ticket (kotak masuk
>   umpan balik berbahasa Indonesia dan Inggris serta perjalanan langsung satu tiket), dan
>   Experiment results (hasil A0 sampai A3).

**§8.3.4, change** "…serta dua tombol, yaitu Setujui dan Tolak disertai alasan. Alasan penolakan masuk ke data pelatihan ulang." **to:**

> …serta tiga tombol, yaitu Approve (setujui), Request changes (minta perubahan), dan Reject and
> stop (tolak dan hentikan). Alasan wajib diisi untuk setiap keputusan, disamarkan dari PII, lalu
> dicatat di audit_log. Purwarupa belum memakai alasan tersebut sebagai data pelatihan ulang.

**Add at the end of §8.3.5:**

> Catatan implementasi: tampilan Agents belum menampilkan host dan denyut terakhir, dan laporan
> DORA pada tampilan Monitoring bersifat ilustratif. Tanpa backend, dasbor beralih ke mode replay,
> dan setiap panel diberi label sumber datanya (Live, Simulated by backend, Replay, Report model,
> atau Recorded).

**§8.3.6, first bullet:** change "…dalam 30 detik (jendela pembatalan)." to "…dalam 30 detik (jendela pembatalan); fitur ini belum diimplementasikan pada purwarupa." **Add two bullets:**

> - Animasi mengikuti pengaturan prefers-reduced-motion: tidak ada yang berjalan sendiri, setiap
>   langkah tetap dapat dibuka, dan setiap animasi memiliki versi teks.
> - Dasbor tersedia dalam mode terang dan gelap serta tiga ukuran teks.

### 11. §8.4 Fitur Unggulan, Tabel 36

| Fitur | Change |
|---|---|
| Migrasi agen | Cara demonstrasi: "Tampilan Agents, tombol 'Investigate on the real nodes', lalu animasi jalur migrasi dan penghitung byte" |
| Laporan performa | Deskripsi: "Perbandingan mode statis dan bergerak berdasarkan model biaya Subbab 5.4 (8.190 MB dalam ±655 detik berbanding 84 MB dalam ±27 detik)". Cara demonstrasi: "Sakelar 'Static pull / Mobile agent' pada tampilan Agents" |
| Keamanan berlapis | Cara demonstrasi: "Centang 'Put a test secret in the draft change' sebelum memulai tiket; pemindaian rahasia menghentikan draf, dan Request changes membuat Worker-Impl menulis ulang draf tanpa rahasia" |
| Koreksi manusia | Deskripsi: "Setiap gerbang dapat disetujui, diminta perubahan, atau ditolak dengan alasan; koreksi dicatat di audit_log (belum dipakai sebagai label pelatihan)". Cara demonstrasi: "Pada gerbang otonomi, pilih Request changes dengan koreksi eksplisit, misalnya 'severity should be High', lalu tunjukkan entrinya pada Decision trace" |
| Simulasi kasus nyata | Cara demonstrasi: "Tampilan Overview memutar ulang Subbab 8.5; Run a ticket menjalankan keluhan FB-001 secara langsung" |

### 12. §8.5, after the paragraph that introduces Tabel 37

**Add:**

> Tampilan Overview pada dasbor memutar ulang linimasa ini sebagai data ilustratif. Ketika keluhan
> serupa (FB-001) dijalankan langsung, angka berasal dari simulator berbenih sehingga dapat berbeda
> dari Tabel 37. Misalnya, Worker-QA memilih sekitar 100 dari 3.400 tes dalam anggaran 8 menit, dan
> skor risiko rilis sekitar 0,25.

### 13. §9.4, Tabel 41, row "Pelanggaran kebijakan yang lolos"

**Now:** "Nol rilis penuh tanpa persetujuan; uji injeksi 20 pelanggaran belum dilaporkan"

**Replace with:** "Nol rilis penuh tanpa persetujuan; uji injeksi: 20 pelanggaran sintetis diblokir dan 0 lolos (security_injection_summary.csv)"

### 14. §9.6, Tabel 43: add a row

| Jenis | Ancaman | Mitigasi |
|---|---|---|
| Internal | Kebocoran label: setiap judul tiket sintetis memuat frasa severity-nya (misalnya "critical data loss"), sehingga macro-F1 bernilai 1,00 pada semua konfigurasi | Dinyatakan sebagai keterbatasan. Generator tidak diubah agar angka laporan tetap dapat direproduksi; evaluasi lanjutan memakai tiket tanpa frasa label |

### 15. §10.1, item 4, last sentence

**Now:** "Purwarupa telah mewujudkan catatan audit dan jeda persetujuan."

**Replace with:** "Purwarupa telah mewujudkan catatan audit, enam jenis gerbang, dan alur sembilan agen yang dapat ditelusuri pada tampilan Decision trace."

### 16. §10.2 Keterbatasan, items 4 and 5

**Item 4, replace with:**

> 4. Model bahasa besar hanya terhubung secara opsional (model gratis OpenRouter untuk triase dan
>    catatan peninjau) dan tidak dipakai pada percobaan. Karena itu, biaya dan latensi LLM belum
>    terukur, dan jumlah token hanya berupa estimasi.

**Item 5, replace with:**

> 5. Alur dari umpan balik sampai pemantauan sudah berjalan menyeluruh melalui sembilan agen, tetapi
>    repositori, CI, deployment, dan telemetri masih berupa simulator berbenih. Model terlatih pada
>    modul RCA dan RL tetap luring, dan alur langsung memakai padanannya yang lebih sederhana.
>    Metrik DORA dan hasil deployment pada percobaan dibangkitkan oleh harness.

**Add at the end of the paragraph:**

> Selain itu, pencarian duplikat pada alur langsung bersifat leksikal sehingga belum mencocokkan
> laporan lintas bahasa, peninjau dicatat dengan nama tanpa autentikasi, dan jendela pembatalan
> 30 detik belum diimplementasikan.

### 17. §10.3 Rekomendasi Pengembangan

**Tabel 44, row "Adaptive AI":** change "…dari koreksi manusia pada Approval Inbox." to "…dari koreksi manusia pada tampilan Human reviews."

**The sentence after Tabel 44, replace with:**

> Selain enam arah tersebut, langkah terdekat yang paling bermanfaat adalah mengganti simulator
> dengan repositori, CI, jalur rilis, dan telemetri nyata, memindahkan model luring (MiniLM dan
> FAISS, GraphSAGE, PPO/DQN) ke alur langsung, lalu mengevaluasinya pada data tiket dan CI publik
> yang dipisah secara kronologis dengan ukuran mutu tugas yang nyata.

### 18. Bab 12.1 Struktur Repositori

**Now:** "Struktur repositori yang kami sarankan tersaji berikut ini." and the old tree.

**Replace with** "Struktur repositori saat ini tersaji berikut ini." **and:**

Each line is at most 80 characters, which is what fits in the report's 8 pt Courier box.

```
t2d-mas/
├── README.md                 # cara menjalankan: mode lokal atau Docker
├── docker-compose.yml        # orkestrator + 6 node + redis + postgres
├── agents/                   # orkestrator FastAPI dan agen: scouts, brokers,
│                             # workers, security_policy, pipeline, tools
├── triage/                   # embedder, dedup, severity, gate (luring)
├── rca/                      # graph_builder, model, explain, baseline
├── envs/                     # test_prioritization, canary_deploy
├── data/                     # schema.sql (enam tabel), loaders, preprocess
├── eval/                     # runner, metrics, security_injection, stats,
│                             # report, compare_runs
├── frontend/                 # dasbor React: delapan tampilan dengan animasi
├── deliverables/             # slide dan panduan demo
├── docs/                     # ide awal, laporan akhir, audit
└── results/                  # keluaran eksperimen bertanggal
```

### 19. Lampiran A, Tabel 46

Delete item 4 ("Jumlah instansiasi agen tidak konsisten…"); item 2 above makes §4.4 say eleven,
matching Tabel 14, §5.3 and §8.1. Renumber the remaining items.

### 20. Lampiran B, after the first paragraph

**Add:**

> Catatan: spesifikasi berikut dicatat sebagaimana dipakai saat pembangunan. Implementasi akhir
> menyimpang pada beberapa butir. Pada B.4, skema berisi enam tabel dan mock_api/ dihapus. Pada B.5,
> kelas dasar agen adalah StageAgent pada agents/stage_agent.py (base.py dihapus), consumer group
> Redis dihapus, dan orkestrator memiliki enam jenis gerbang. Pada B.6, dasbor memiliki delapan
> tampilan dan memakai CSS biasa, bukan Tailwind. Pada B.7, akurasi top-k RCA dihitung pada
> rca/evaluation.py, bukan eval/metrics.py. Rinciannya tersedia pada docs/AUDIT.md di repositori.

## Part 3: figures

- **Gambar 3 (diagram relasi entitas):** redraw it with the six tables in Tabel 28. The foreign
  keys are code_changes → tickets, deployments → code_changes, deployments → tickets and
  deployments → deployments (rollback_of). audit_log stores ticket_id without a foreign key, so it
  keeps entries for every ticket; policies and slo_baselines stand alone.
- **Gambar 4 (wireframe dasbor):** optional. Keep the wireframe as the design, or replace it with
  a screenshot of the Tickets board or the Run a ticket view.
- **Gambar 1:** no change needed. Its three red gates are the design's gates, and item 3 above
  explains the other three.
