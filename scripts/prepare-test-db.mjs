// Migrate a pre-created disposable database. Never accepts the application's URL.
import postgres from 'postgres';
import { readFile, readdir } from 'node:fs/promises';
const url=process.env.TEST_DATABASE_URL;
if(!url || !new URL(url).pathname.endsWith('_test'))throw new Error('Set TEST_DATABASE_URL to a separate database whose name ends with _test.');
const sql=postgres(url,{max:1,prepare:false});
try {
 const [state]=await sql`select to_regclass('public.pairs') as pairs`;
 if(state.pairs) console.log('Test schema already exists. Use a fresh database when changing migrations.');
 else for(const file of (await readdir('supabase/migrations')).filter(f=>f.endsWith('.sql')).sort()) {await sql.unsafe(await readFile(`supabase/migrations/${file}`,'utf8'));console.log('Applied',file);}
}finally {await sql.end();}
