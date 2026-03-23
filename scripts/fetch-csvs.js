// Fetches the latest CSV data from the public Google Sheet and writes
// each tab to src/imports/. Run with: npm run fetch-data
// Requires Node 18+ (uses built-in fetch).

import { writeFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

const SHEET_ID = '1owsUDceWy-sG258SE8Z-gwTDLOQwIqAr6ADdfOln-2E';
const IMPORTS_DIR = join(__dirname, '..', 'src', 'imports');

const SHEETS = [
  {
    tab: 'classification_options',
    filename: 'Weapons_Classifications__Small_Arms_-_classifications.csv',
  },
  {
    tab: 'classification_definitions',
    filename: 'Weapons_Classifications__Small_Arms_-_classification_level_definitions.csv',
  },
  {
    tab: 'characteristic_definitions',
    filename: 'Weapons_Classifications__Small_Arms_-_characteristic_values.csv',
  },
  {
    tab: 'characteristic_options',
    filename: 'Weapons_Classifications__Small_Arms_-_characteristic_options.csv',
  },
];

async function fetchSheet({ tab, filename }) {
  const url = `https://docs.google.com/spreadsheets/d/${SHEET_ID}/gviz/tq?tqx=out:csv&sheet=${encodeURIComponent(tab)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch tab "${tab}": ${res.status} ${res.statusText}`);
  const csv = await res.text();
  const dest = join(IMPORTS_DIR, filename);
  writeFileSync(dest, csv, 'utf8');
  console.log(`  wrote ${filename}`);
}

console.log('Fetching CSVs from Google Sheets...');
for (const sheet of SHEETS) {
  await fetchSheet(sheet);
}
console.log('Done.');
