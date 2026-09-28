"""Validate every CSV row, then atomically upsert valid, stable-ID pairs."""
import argparse
import csv
import os
import sys
from urllib.parse import urlsplit
from uuid import UUID

REQUIRED = ('id', 'question', 'category', 'answer_real', 'answer_fake', 'fabricated_span', 'hallucination_type', 'explanation', 'origin', 'dataset_version')
COLUMNS = (*REQUIRED, 'source_url', 'model_name', 'is_attention_check', 'is_active')
TYPES = {'wrong_number', 'wrong_entity', 'wrong_date', 'invented_citation', 'other'}


def validate(row):
    errors = [f'{key}: required' for key in REQUIRED if not row.get(key, '').strip()]
    result = {key: row.get(key, '').strip() for key in COLUMNS}
    # Exact answer/span text is preserved, rather than normalizing research content.
    for key in ('answer_real', 'answer_fake', 'fabricated_span'):
        result[key] = row.get(key, '')
    try:
        result['id'] = str(UUID(result['id']))
    except ValueError:
        errors.append('id: must be a UUID')
    if result['hallucination_type'] not in TYPES:
        errors.append('hallucination_type: invalid value')
    if result['origin'] not in {'natural', 'synthetic'}:
        errors.append('origin: invalid value')
    if not result['fabricated_span'] or result['fabricated_span'] not in result['answer_fake']:
        errors.append('fabricated_span: must be an exact nonempty substring of answer_fake')
    for key, default in (('is_attention_check', False), ('is_active', True)):
        raw = result[key].lower()
        if raw not in {'', 'true', 'false', '1', '0'}:
            errors.append(f'{key}: must be true or false')
        result[key] = default if not raw else raw in {'true', '1'}
    url = result['source_url']
    if url:
        try:
            parsed = urlsplit(url)
            if parsed.scheme not in {'http', 'https'} or not parsed.hostname or any(c.isspace() for c in url) or parsed.username or parsed.password:
                raise ValueError()
            _ = parsed.port
        except ValueError:
            errors.append('source_url: must be a valid HTTP(S) URL without credentials')
    result['source_url'] = url or None
    result['model_name'] = result['model_name'] or None
    return result, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv_path')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--deactivate-missing', action='store_true')
    args = parser.parse_args()
    valid, invalid, seen = [], 0, set()
    with open(args.csv_path, newline='', encoding='utf-8-sig') as source:
        reader = csv.DictReader(source)
        missing = set(REQUIRED) - set(reader.fieldnames or [])
        if missing:
            parser.error('Missing columns: ' + ', '.join(sorted(missing)))
        for line, row in enumerate(reader, 2):
            if None in row or any(value is None for value in row.values()):
                print(f'Row {line}: wrong number of CSV fields')
                invalid += 1
                continue
            item, errors = validate(row)
            if item['id'] in seen:
                errors.append('id: duplicate in CSV')
            seen.add(item['id'])
            if errors:
                invalid += 1
                print(f'Row {line}: ' + '; '.join(errors))
            else:
                valid.append(item)
    print(f'{len(valid)} valid rows; {invalid} invalid rows.')
    if args.dry_run:
        return int(invalid > 0)
    if args.deactivate_missing and (invalid or not valid):
        parser.error('--deactivate-missing requires a nonempty CSV with no invalid rows')
    if not valid:
        return 1
    if not os.environ.get('DATABASE_URL'):
        parser.error('Set DATABASE_URL before importing (not needed for --dry-run)')
    import psycopg
    from psycopg import sql
    try:
        with psycopg.connect(os.environ['DATABASE_URL']) as conn:
            with conn.cursor() as cur:
                query = sql.SQL('insert into pairs ({}) values ({}) on conflict (id) do update set {}').format(
                    sql.SQL(',').join(map(sql.Identifier, COLUMNS)),
                    sql.SQL(',').join(sql.Placeholder() for _ in COLUMNS),
                    sql.SQL(',').join(sql.SQL('{} = excluded.{}').format(sql.Identifier(k), sql.Identifier(k)) for k in COLUMNS if k != 'id'))
                cur.executemany(query, [[item[k] for k in COLUMNS] for item in valid])
                if args.deactivate_missing:
                    cur.execute('update pairs set is_active=false where is_active and not (id = any(%s::uuid[]))', ([r['id'] for r in valid],))
                    print(f'Deactivated {cur.rowcount} missing pairs.')
    except psycopg.Error:
        print('Import failed; transaction rolled back. Check connectivity, schema, and whether an assigned pair was edited.', file=sys.stderr)
        return 1
    print(f'Imported {len(valid)} pairs.')
    return int(invalid > 0)


if __name__ == '__main__':
    sys.exit(main())
