import Papa from 'papaparse';
import characteristicOptionsCsv from '../../imports/Weapons_Classifications__Small_Arms_characteristic_options.csv?raw';
import characteristicValuesCsv from '../../imports/Weapons_Classifications__Small_Arms_characteristic_values.csv?raw';
import classificationsCsv from '../../imports/Weapons_Classifications__Small_Arms_classifications.csv?raw';

export type CharacteristicType = 'how held' | 'bore_type' | 'loading' | 'action mechanism';

export interface CharacteristicOption {
  id: string;
  name: string;
  guidance: string;
  pdfPages?: number[];
  imagePage?: number;
}

export interface Characteristic {
  id: CharacteristicType;
  name: string;
  description: string;
  options: CharacteristicOption[];
}

export interface WeaponClassification {
  id: string;
  name: string;
  description: string;
  group: string;
  type: string;
  subType?: string;
  pdfPages?: number[];
  imagePage?: number;
  imageUrl?: string;
  characteristics: {
    'how held'?: string;
    'bore_type'?: string;
    'loading'?: string;
    'action mechanism'?: string;
  };
}

export const PDF_URL = 'https://armamentresearch.com/wp-content/uploads/2022/08/The-ARES-Arms-Munitions-Classification-System-ARCS-ver1.3-public-release.pdf';

// Parse comma-separated page numbers, adding +1 to each for PDF title page offset
function parsePages(pageStr: string | undefined): number[] | undefined {
  if (!pageStr || pageStr.trim() === '' || pageStr.trim() === 'NA') return undefined;
  const pages = pageStr.split(',').map(p => parseInt(p.trim()) + 1).filter(n => !isNaN(n));
  return pages.length > 0 ? pages : undefined;
}

// Parse a single page number (+1 offset), using the first value if comma-separated
function parseSinglePage(pageStr: string | undefined): number | undefined {
  if (!pageStr || pageStr.trim() === '' || pageStr.trim() === 'NA') return undefined;
  const n = parseInt(pageStr.split(',')[0].trim()) + 1;
  return isNaN(n) ? undefined : n;
}

// Map CSV characteristic column values to CharacteristicType IDs.
// The CSV uses different spellings: 'bore type' vs 'bore_type', trailing spaces, etc.
const CHAR_ID_MAP: Record<string, CharacteristicType> = {
  'how held': 'how held',
  'bore_type': 'bore_type',
  'bore type': 'bore_type',
  'loading': 'loading',
  'action mechanism': 'action mechanism',
};

const CHARACTERISTIC_ORDER: CharacteristicType[] = [
  'how held',
  'bore_type',
  'loading',
  'action mechanism',
];

const CHARACTERISTIC_DISPLAY_NAMES: Record<CharacteristicType, string> = {
  'how held': 'How Held (Grip/Bracing)',
  'bore_type': 'Bore Type',
  'loading': 'Loading Mechanism',
  'action mechanism': 'Action Mechanism',
};

// --- Parse characteristic descriptions from characteristic_values.csv ---
const charDescriptions: Partial<Record<CharacteristicType, string>> = {};
const valuesResult = Papa.parse<Record<string, string>>(characteristicValuesCsv, {
  header: true,
  skipEmptyLines: true,
});
for (const row of valuesResult.data) {
  const charKey = (row['characteristic'] ?? '').trim().toLowerCase();
  const id = CHAR_ID_MAP[charKey];
  if (id) {
    charDescriptions[id] = row['broad guidance'] ?? '';
  }
}

// --- Parse characteristic options from characteristic_options.csv ---
const charOptions: Record<CharacteristicType, CharacteristicOption[]> = {
  'how held': [],
  'bore_type': [],
  'loading': [],
  'action mechanism': [],
};
const optionsResult = Papa.parse<Record<string, string>>(characteristicOptionsCsv, {
  header: true,
  skipEmptyLines: true,
});
for (const row of optionsResult.data) {
  const charKey = (row['characteristic'] ?? '').trim().toLowerCase();
  const id = CHAR_ID_MAP[charKey];
  if (!id) continue;

  // Image page numbers are the visual reference pages shown in the PDF viewer
  const pdfPages = parsePages(row['ARES_guide_image_page_number']);
  charOptions[id].push({
    id: (row['option'] ?? '').trim().toLowerCase(),
    name: row['option'] ?? '',
    guidance: row['description'] ?? '',
    pdfPages,
    imagePage: pdfPages?.[0],
  });
}

// --- Build CHARACTERISTICS in fixed display order ---
export const CHARACTERISTICS: Characteristic[] = CHARACTERISTIC_ORDER.map(id => ({
  id,
  name: CHARACTERISTIC_DISPLAY_NAMES[id],
  description: charDescriptions[id] ?? '',
  options: charOptions[id],
}));

// --- Parse weapon classifications from classifications.csv ---
const classResult = Papa.parse<Record<string, string>>(classificationsCsv, {
  header: true,
  skipEmptyLines: true,
});

export const WEAPON_CLASSIFICATIONS: WeaponClassification[] = classResult.data.map(row => {
  // pdfPages: text reference page(s); imagePage: figure/image page
  const pdfPages = parsePages(row['ARES_guide_page_number']);
  const imagePage = parseSinglePage(row['ARES_guide_image_page_number']);

  // Characteristic values are lowercased to match option IDs
  const held = (row['How held (grip / bracing)'] ?? '').trim().toLowerCase() || undefined;
  const bore = (row['Bore type'] ?? '').trim().toLowerCase() || undefined;
  const loading = (row['Loading'] ?? '').trim().toLowerCase() || undefined;
  const action = (row['Action mechanism'] ?? '').trim().toLowerCase() || undefined;

  return {
    id: row['id'] ?? '',
    name: row['Name'] ?? '',
    description: (row['Description'] ?? '').trim(),
    group: row['Group'] ?? '',
    type: row['Type'] ?? '',
    subType: (row['Sub-type'] ?? '').trim() || undefined,
    pdfPages,
    imagePage,
    imageUrl: (row['Image URL'] ?? '').trim() || undefined,
    characteristics: {
      ...(held ? { 'how held': held } : {}),
      ...(bore ? { 'bore_type': bore } : {}),
      ...(loading ? { 'loading': loading } : {}),
      ...(action ? { 'action mechanism': action } : {}),
    },
  };
});
