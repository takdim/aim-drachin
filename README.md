# aim-drachin

Web Flask lokal untuk membaca HTML publik dari `tv46.juragan.film` / `juragan.film`.

Fitur:

- Halaman utama menampilkan card tayangan dari homepage.
- Search keyword memakai format query JuraganFilm.
- Klik card membuka halaman detail dan menampilkan iframe player.
- Halaman seri menampilkan tombol episode.
- Detail teknis tetap tersedia untuk iframe, link, gambar, heading, dan meta tag.

## Struktur

```text
app.py
aim_drachin/
  __init__.py
  config.py
  scraper.py
templates/
  index.html
static/
  css/app.css
  js/app.js
```

## Jalankan

```bash
python3 app.py
```

Jika Flask belum tersedia:

```bash
python3 -m pip install -r requirements.txt
```

Buka:

```text
http://127.0.0.1:8000
```

URL default:

```text
https://tv46.juragan.film/?v=1781515282.252
```

Catatan: scraper ini tidak menjalankan JavaScript halaman target, tidak mengunduh media, dan tidak membypass login/proteksi/DRM.
