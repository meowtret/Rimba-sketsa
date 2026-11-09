# Rimba Sketsa

Plugin QGIS untuk membuat sketsa cepat di kanvas peta (teks, titik klik / XY / DMS, garis,
persegi, lingkaran, poligon, buffer) lalu menyeleksi objek layer yang berada di dalam sketsa.
Hasil seleksi tampil di jendela tabel yang bisa disimpan ke ODS atau diekspor menjadi layer memori.

- QGIS 3.22 – 4.x (Qt5 dan Qt6)
- Antarmuka Inggris + Indonesia (mengikuti bahasa UI QGIS)
- Lisensi: GNU GPL v3 atau yang lebih baru

## Asal-usul

Rimba Sketsa adalah turunan **qdrawEVT 2.74** karya François Thévand
(<https://github.com/fthvd/qdrawEVT>), yang berbasis **QDraw** karya Jérémy Kalsron.
Perubahan utama dari qdrawEVT:

- Fitur manajemen krisis Prancis dibuang: mode EVT (layer `POINT/LIGNE/POLYGONE_EVENEMENT`),
  pembuatan layer event di Settings, dan installer plugin Gestion_crise.
- `sys.excepthook` dan pengalihan `stdout/stderr` global dibuang. Versi asli menampilkan error
  dari plugin mana pun sebagai dialog berbahasa Prancis.
- Ikon flat yang lebih sederhana.
- Terjemahan Indonesia dan bantuan Inggris + Indonesia.
- Perbaikan bug: membatalkan pilihan grup tidak lagi menghapus layer milik pengguna;
  KeyError saat menyorot garis di jendela hasil seleksi.

## Struktur

| File | Isi |
|---|---|
| `rimba_sketsa.py` | Kelas utama `RimbaSketsa` (toolbar, alat gambar, seleksi) |
| `drawtools.py` | Map tool gambar + dialog XY / DMS / ukuran |
| `layer_dialog.py` | Dialog nama gambar & pilihan layer tujuan |
| `AttributesTable.py` | Jendela hasil seleksi, simpan ODS, ekspor layer memori |
| `settings.py` | Jendela pengaturan warna/opasitas/huruf |
| `i18n/` | `rimba_sketsa_id.ts/.qm` + kamus `translations_id.py` |
| `help/` | `readme_id.html`, `readme_en.html` |

## Memperbarui terjemahan

1. Tambahkan teks baru dalam bahasa Inggris lewat `self.tr("...")`.
2. Tambahkan padanannya di `i18n/translations_id.py`.
3. Jalankan `python tools/build_i18n.py` (butuh `lrelease` dari Qt Linguist,
   misalnya `pyside6-lrelease` dari paket pip `pyside6-essentials`).

## Paket ZIP

Folder `tools/`, `i18n/*.py`, `i18n/*.ts`, `README.md`, dan `.git` tidak ikut dimasukkan ke ZIP plugin.
