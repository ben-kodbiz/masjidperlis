# data-entry — daily data entry (local CSV / Excel)

This folder is for **non-technical daily use**: edit the CSV files in Excel
(they open normally, no technical skills needed), then run one command. No
Google account, no API key, no config editing required.

## The four files

| File | What it holds |
| ---- | ------------- |
| `1-kategori.csv` | Event categories (e.g. Kuliah, Tazkirah) |
| `2-penceramah.csv` | Speakers / penceramah |
| `3-masjids.csv` | Masjids |
| `4-acara.csv` | Events (acara) |

Each file already has its column names in row 1 — **just add your data
underneath the header row** and save.

## Example rows (copy the format, then delete this section)

`1-kategori.csv`:

```csv
id,Nama
,kuliah
,tazkirah
```

`2-penceramah.csv`:

```csv
id,Nama,Penerangan
,ustaz-ahmad,Ustaz Ahmad Firdaus
```

`3-masjids.csv`:

```csv
id,Nama,Daerah,Negeri,Alamat,Latitud,Longitud,Kenalan,Laman web
,masjid-alwi,Kangar,Perlis,Jalan Tuanku Syed Putra 01000 Kangar,6.4405,100.1952,,
```

`4-acara.csv`:

```csv
id,Tajuk,Masjid,Tarikh,Mula,Tamat,Penceramah,Kategori,Lokasi,Penerangan,Status,Jenis ulangan,Hari ulangan,Mula ulangan,Tamat ulangan,Pengecualian
,Acara Ujian,Masjid Alwi,2026-08-20,20:00,21:00,Ustaz Ahmad Firdaus,kuliah,,Siri mingguan,published,weekly,"monday,friday",2026-08-20,2026-12-31,"2026-08-28,2026-09-04"
```

Notes:
- Leave `id` blank on new rows (it is generated and stays stable).
- `Tarikh` = `YYYY-MM-DD`, `Mula`/`Tamat` = `HH:MM`.
- `Masjid` / `Penceramah` / `Kategori` accept the name **or** the id.
- `Status`: `published`, `draft`, `cancelled`, `postponed`, `completed`.
- A value containing a comma (`Hari ulangan`, `Pengecualian`) must be quoted.
- Importing is **add + update only** — it never deletes your data.
- To update an existing row, keep its `id`; a blank `id` adds a new row.

## Daily use

```bash
./data-entry/update.sh
```

This imports the CSVs into `data/` (validating first) and prints the two
commands that publish the site:

```bash
git add data/ && git commit -m "data: update from CSV" && git push
```

After the push, GitHub rebuilds the site automatically (check the **Actions**
tab for the green "Deploy to GitHub Pages" run). You can also preview first:

```bash
./data-entry/update.sh           # or: python3 tools/import_google_sheet.py --config data-entry/config.json --dry-run
python3 -m http.server 8000 --directory public
```
