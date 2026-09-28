# Research data tools

Python 3.11+. Install `requirements.txt` in a virtual environment. Set `DATABASE_URL` in the process environment (never commit it).

`python import_pairs.py data/sample_pairs.csv --dry-run` validates without a database.
`python import_pairs.py data/sample_pairs.csv` imports valid rows in a transaction.
`--deactivate-missing` marks other pairs inactive; it never deletes. This option refuses a CSV with invalid rows or no valid rows.

The sample CSV is for development only. Dataset generation and analysis are owned by Shravani.
