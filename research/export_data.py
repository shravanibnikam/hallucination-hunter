"""Export raw research rows with quality flags; no silent quality exclusions."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import sys

QUERY = """
with device_rounds as (
 select id, (case when device_id is not null then row_number() over (partition by device_id order by created_at, id) end)::text as device_round_number
 from sessions)
select g.id as guess_id, g.session_item_id, g.session_id, g.pair_id,
 g.chosen_side, g.judgment, g.is_correct, g.confidence, g.response_time_ms,
 g.flagged_too_fast, g.created_at as guess_created_at, g.app_version as guess_app_version,
 g.dataset_version as guess_dataset_version,
 s.created_at as session_created_at, s.condition, s.consent_given_at, s.age_confirmed,
 s.nickname, s.device_type, s.ai_usage_frequency, s.background, s.ai_knowledge_rating,
 s.total_items, s.completed, s.completed_at, s.final_score, s.best_streak,
 s.failed_attention_check, s.is_pilot, s.device_id, r.device_round_number, s.app_version as session_app_version,
 i.position, i.fake_shown_on, i.shown_answer, i.served_at,
 p.question, p.category, p.answer_real, p.answer_fake, p.fabricated_span,
 p.hallucination_type, p.explanation, p.source_url, p.model_name, p.origin,
 p.is_attention_check, p.is_active, p.dataset_version as pair_dataset_version,
 p.created_at as pair_created_at
from guesses g join sessions s on s.id=g.session_id
join session_items i on i.id=g.session_item_id join pairs p on p.id=g.pair_id
join device_rounds r on r.id=s.id
where (%s or not s.is_pilot)
order by g.created_at, g.id
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include-pilot', action='store_true')
    args = parser.parse_args()
    if not os.environ.get('DATABASE_URL'):
        parser.error('Set DATABASE_URL before exporting')
    import pandas as pd
    import psycopg
    folder = Path(__file__).resolve().parent / 'data' / 'exports'
    folder.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    path = folder / f'guesses_{timestamp}.csv'
    total = 0
    try:
        with psycopg.connect(os.environ['DATABASE_URL']) as conn:
            # A named cursor streams one consistent query without loading all rows.
            with conn.cursor(name='research_export') as cur:
                cur.execute(QUERY, (args.include_pilot,))
                with path.open('x', encoding='utf-8', newline='') as output:
                    first = True
                    while True:
                        rows = cur.fetchmany(10000)
                        columns = [column.name for column in cur.description]
                        if not rows:
                            if first:
                                pd.DataFrame(columns=columns).to_csv(output, index=False)
                            break
                        pd.DataFrame.from_records(rows, columns=columns).to_csv(output, index=False, header=first)
                        first = False
                        total += len(rows)
    except psycopg.Error:
        if path.exists():
            path.unlink()
        print('Export failed. No complete export was saved. Check database access.', file=sys.stderr)
        return 1
    print(f'Exported {total} guesses to {path}')
    print('Raw working data: review aliases and timestamps before anonymized publication.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
