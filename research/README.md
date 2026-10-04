# Research data tools

Python 3.11+. Install `requirements.txt` in a virtual environment. Set `DATABASE_URL` in the process environment (never commit it).

`python import_pairs.py data/sample_pairs.csv --dry-run` validates without a database.
`python import_pairs.py data/sample_pairs.csv` imports valid rows in a transaction.
`--deactivate-missing` marks other pairs inactive; it never deletes. This option refuses a CSV with invalid rows or no valid rows.

The sample CSV is for development only. Dataset generation and analysis are owned by Shravani.

`python export_data.py` writes a timestamped CSV in ignored `data/exports/`. `--include-pilot` includes pilot sessions. Exports retain incomplete rounds and quality flags rather than silently excluding them. They stream in chunks through a database cursor.

These are private working exports, not publication-ready anonymized datasets: optional aliases and precise timestamps require review before release. No dataset-generation or analysis code is supplied.
