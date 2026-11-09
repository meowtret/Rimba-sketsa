# -*- coding: utf-8 -*-
"""Kamus terjemahan Inggris -> Indonesia untuk Rimba Sketsa.

Dipakai oleh tools/build_i18n.py untuk membuat i18n/rimba_sketsa_id.ts
lalu dikompilasi menjadi i18n/rimba_sketsa_id.qm dengan lrelease.
Kunci kamus = teks sumber (Inggris) persis seperti di dalam self.tr().
"""

ID = {
    # ------------------------------------------------------------------
    # Toolbar, menu, status bar
    # ------------------------------------------------------------------
    "Text drawing tool": "Alat tulis teks",
    "Point drawing tool": "Alat gambar titik",
    "XY Point drawing tool": "Titik dari koordinat XY",
    "DMS Point drawing tool": "Titik dari koordinat DMS",
    "Line drawing tool": "Alat gambar garis",
    "Rectangle drawing tool": "Alat gambar persegi",
    "Circle drawing tool": "Alat gambar lingkaran",
    "Polygon drawing tool": "Alat gambar poligon",
    "Buffer drawing on objects in selected layer": "Buffer pada objek di layer terpilih",
    "Buffer drawing with polygonal selection of objects in the selected layer":
        "Buffer dengan seleksi poligon atas objek di layer terpilih",
    "Buffer drawing tool on the selected layer": "Buffer pada objek di layer terpilih",
    "Polygon buffer drawing tool on the selected layer": "Buffer poligon pada layer terpilih",
    "Settings": "Pengaturan",
    "Help / User manual": "Bantuan / Panduan",
    "Left click to place a text.": "Klik kiri untuk menempatkan teks.",
    "Left click to place a point.": "Klik kiri untuk menempatkan titik.",
    "Left click to place points. Right click to confirm.":
        "Klik kiri untuk menambah titik. Klik kanan untuk selesai.",
    "Maintain the left click to draw a rectangle.": "Tahan klik kiri lalu seret untuk menggambar persegi.",
    "Maintain the left click to draw a circle. Simple left click to give a perimeter.":
        "Tahan klik kiri lalu seret untuk menggambar lingkaran. Klik kiri sekali untuk mengisi jari-jari.",
    "Select a vector layer in the Layer Tree, then select an entity on the map.":
        "Pilih layer vektor di panel Layers, lalu klik objek di peta.",
    "Length: {value} m": "Panjang: {value} m",
    "Area: {value} m²": "Luas: {value} m²",
    "Drawings": "Sketsa",
    "Selecting...": "Menyeleksi...",
    "Pass": "Lewati",

    # ------------------------------------------------------------------
    # Pesan & dialog utama
    # ------------------------------------------------------------------
    "Error": "Kesalahan",
    "Warning": "Peringatan",
    "WARNING!": "PERINGATAN!",
    "Cancel": "Batal",
    "Close": "Tutup",
    "Start again": "Ulangi",
    "Invalid input !": "Masukan tidak valid!",
    "No selection": "Tidak ada seleksi",
    "No selected items found in visible vector layers.":
        "Tidak ada objek terseleksi pada layer vektor yang tampil.",
    "unknown CRS": "CRS tidak dikenal",
    "Invalid coordinates or projection": "Koordinat atau proyeksi tidak valid",
    "The entered coordinates ({pt}) are not valid for the selected source projection {src}.\n\n"
    "Choose the projection matching the coordinates, then try again.\n\nProject projection: {dst}.":
        "Koordinat yang dimasukkan ({pt}) tidak valid untuk proyeksi sumber {src}.\n\n"
        "Pilih proyeksi yang sesuai dengan koordinat, lalu coba lagi.\n\nProyeksi proyek: {dst}.",
    "The coordinate entry window will reopen automatically after the countdown, or immediately after OK.":
        "Jendela isian koordinat akan terbuka lagi setelah hitung mundur, atau langsung setelah OK.",
    "OK ({s})": "OK ({s})",
    "Coordinate input cancelled or invalid": "Isian koordinat dibatalkan atau tidak valid",
    "No point was created.": "Tidak ada titik yang dibuat.",
    "No object selected": "Tidak ada objek terpilih",
    "No object was found under the click.\n\nPlease click directly on an object of the active layer.":
        "Tidak ada objek di bawah klik.\n\nKlik tepat pada objek di layer aktif.",

    # Buffer
    "Buffer creation": "Pembuatan buffer",
    "Do you want to create a buffer around the selected object?":
        "Buat buffer di sekeliling objek yang dipilih?",
    "Choose whether the selection must use the object itself or a buffer around it.":
        "Pilih apakah seleksi memakai objek itu sendiri atau buffer di sekelilingnya.",
    "Create buffer": "Buat buffer",
    "No buffer": "Tanpa buffer",
    "Buffer size": "Jarak buffer",
    "Enter the buffer size in meters:\n(works only with a metric coordinate reference system)":
        "Masukkan jarak buffer dalam meter:\n(hanya berlaku untuk CRS bersatuan meter)",
    "Perimeter": "Jarak buffer",
    "Give a perimeter in m:\n(works only with metric crs)":
        "Masukkan jarak dalam meter:\n(hanya berlaku untuk CRS bersatuan meter)",
    "You didn't click on a layer's attribute !": "Anda belum mengklik objek pada layer!",
    "You must give a non-null value for a point's or line's perimeter!":
        "Jarak buffer untuk titik atau garis harus lebih dari nol!",
    "There is no selected layer, or it is not vector nor visible!":
        "Tidak ada layer terpilih, atau layer bukan vektor / tidak tampil!",

    # Nama gambar
    "Circle name": "Nama lingkaran",
    "Enter a name for the circle:": "Beri nama lingkaran:",
    "Circle…": "Lingkaran…",
    "Rectangle name": "Nama persegi",
    "Enter a name for the rectangle:": "Beri nama persegi:",
    "Rectangle…": "Persegi…",
    "Polygon name": "Nama poligon",
    "Enter a name for the polygon:": "Beri nama poligon:",
    "Polygon…": "Poligon…",
    "Buffer name": "Nama buffer",
    "Enter a name for the buffer:": "Beri nama buffer:",
    "Buffer…": "Buffer…",

    # Seleksi & grup
    "Choosing a selection": "Seleksi objek",
    "{name} drawn. Make a selection within its extent?":
        "{name} sudah digambar. Seleksi objek di dalam cakupannya?",
    "No group found": "Grup tidak ditemukan",
    "No group exists in the project.\nCreate a group and choose the layers to put in it:":
        "Belum ada grup di proyek ini.\nBuat grup lalu pilih layer yang dimasukkan:",
    "New group name": "Nama grup baru",
    "Available layers": "Layer yang tersedia",
    "You must name the group.": "Grup harus diberi nama.",
    "Group created": "Grup dibuat",
    "The {new_group_name} group has been created and the selected layers have been moved.":
        "Grup {new_group_name} sudah dibuat dan layer terpilih sudah dipindahkan.",
    "Choose a group for selection": "Pilih grup untuk diseleksi",
    "Choose a group from the list:": "Pilih grup dari daftar:",
    "No groups": "Tidak ada grup",
    "All groups are already checked.": "Semua grup sudah dicentang.",
    "No layer or group is selected. Start again.": "Belum ada layer atau grup yang dipilih. Ulangi lagi.",
    "Selection not possible. The checked layer is not a polygon.":
        "Seleksi tidak bisa dilakukan. Layer yang dicentang bukan poligon.",
    "Selection not possible. No layer is selected in the Layer Manager.":
        "Seleksi tidak bisa dilakukan. Belum ada layer yang dipilih di panel Layers.",
    "End of selection": "Seleksi selesai",
    "The {sel_group} group has been unchecked.": "Centang grup {sel_group} sudah dilepas.",

    # Bantuan
    "Rimba Sketsa Help": "Bantuan Rimba Sketsa",
    "No help file was found in the 'help' folder.": "File bantuan tidak ditemukan di folder 'help'.",
    "Unable to read the help file: {error}": "File bantuan tidak bisa dibaca: {error}",

    # ------------------------------------------------------------------
    # Dialog nama gambar (SketsaLayerDialog)
    # ------------------------------------------------------------------
    "Drawing": "Gambar",
    "Give a name to the item:": "Beri nama objek:",
    "Name…": "Nama…",
    "Text…": "Teks…",
    "Add text": "Tambah teks",
    "Type the text to display:": "Ketik teks yang ditampilkan:",
    "Add point": "Tambah titik",
    "Give a name to the point:": "Beri nama titik:",
    "Point…": "Titik…",
    "Add line": "Tambah garis",
    "Give a name to the line:": "Beri nama garis:",
    "Line…": "Garis…",
    "Add polygon": "Tambah poligon",
    "Give a name to the polygon:": "Beri nama poligon:",
    "Buffer selection": "Seleksi buffer",
    "Name this selection (buffer):": "Beri nama seleksi (buffer) ini:",
    "Add to an existing layer": "Tambahkan ke layer yang sudah ada",

    # ------------------------------------------------------------------
    # Pengaturan
    # ------------------------------------------------------------------
    "Rimba Sketsa - Settings": "Rimba Sketsa - Pengaturan",
    "Change the drawing color": "Ganti warna gambar",
    "Change text font": "Ganti huruf teks",
    "Change text color": "Ganti warna teks",
    "Opacity": "Opasitas",

    # ------------------------------------------------------------------
    # Dialog koordinat & ukuran (drawtools)
    # ------------------------------------------------------------------
    "Rectangle size": "Ukuran persegi",
    "Give a size in m:": "Masukkan ukuran dalam meter:",
    "Width:": "Lebar:",
    "Height:": "Tinggi:",
    "Radius": "Jari-jari",
    "Give a radius in m:": "Masukkan jari-jari dalam meter:",
    "DMS Point Tool": "Titik dari koordinat DMS",
    "Latitude": "Lintang",
    "Longitude": "Bujur",
    "Degrees": "Derajat",
    "Minutes": "Menit",
    "Seconds": "Detik",
    "Direction": "Arah",
    "Projection": "Proyeksi",

    # ------------------------------------------------------------------
    # Jendela hasil seleksi (AttributesTable)
    # ------------------------------------------------------------------
    "Save this tab's results": "Simpan hasil tab ini",
    "Save all results": "Simpan semua hasil",
    "Export the selection as a memory layer": "Ekspor seleksi menjadi layer memori",
    "Export all tabs as a memory layer": "Ekspor semua tab menjadi layer memori",
    "Zoom to selected attributes": "Zoom ke baris terpilih",
    "Highlight feature's geometry": "Sorot geometri objek",
    "Highlight feature's centroid": "Sorot titik tengah objek",
    "Loading...": "Memuat...",
    "Rename window": "Ganti judul jendela",
    "Enter a new title:": "Masukkan judul baru:",
    "Apply": "Terapkan",
    "Sheet": "Lembar",
    "Selection made in": "Seleksi di",
    "Selection made in %1 perimeter": "Seleksi di dalam %1",
    "Save in...": "Simpan ke...",
    "OpenDocument Spreadsheet (*.ods)": "OpenDocument Spreadsheet (*.ods)",
    "Open file?": "Buka file?",
    "Open": "Buka",
    "Information": "Informasi",
    "No data to save.": "Tidak ada data untuk disimpan.",
    "Extracts in {name}": "Hasil di {name}",
    "Extract {}": "Hasil {}",
    "Extracts in {}": "Hasil di {}",
    "Extract {title}": "Hasil {title}",
    "Cannot create export folder.": "Folder ekspor tidak bisa dibuat.",
    "No active tab found.": "Tidak ada tab aktif.",
    "ODS workbook created successfully:\n\n{path}\n\nOpen file?":
        "File ODS berhasil dibuat:\n\n{path}\n\nBuka file?",
    "Session": "Sesi",
    "No items were selected": "Tidak ada objek yang terpilih",
    "No application accepted the ODS file.": "Tidak ada aplikasi yang bisa membuka file ODS.",
    "[highlight_features] Status bar update failed: {e_sb}":
        "[highlight_features] Gagal memperbarui status bar: {e_sb}",
    "Selected items: {nb} Area: {area} m²": "Objek terpilih: {nb}  Luas: {area} m²",
    "Selected items: {nb} - Length: {length} m": "Objek terpilih: {nb}  Panjang: {length} m",
    "Selected items: {nb}": "Objek terpilih: {nb}",
    "Unable to replace the existing file.\nPlease close it if it is open in another application, then try again.\n\n{path}":
        "File lama tidak bisa ditimpa.\nTutup file itu jika sedang dibuka di aplikasi lain, lalu coba lagi.\n\n{path}",
    "Unable to write file:\n{e_rep}": "File tidak bisa ditulis:\n{e_rep}",
    "Unable to open the ODS file automatically:\n\n{e_open}":
        "File ODS tidak bisa dibuka otomatis:\n\n{e_open}",
    "Tab {index}": "Tab {index}",
}
