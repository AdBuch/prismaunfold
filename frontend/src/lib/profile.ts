/**
 * Reader profile (contract: docs/READER_PROFILE.md).
 *
 * Stored on this device only (localStorage). Nothing here is sent to PrismUnfold,
 * to AI workers or to anyone else. Weights are relevance signals for selection and
 * ordering, never preferences about what is true. Behavioural personalisation and
 * reading history are off unless the reader turns them on.
 */
import { parsePrefs, type Preferences } from './prefs.ts';

export type Depth = 'brief' | 'standard' | 'deep';

export interface ReaderProfile {
  version: 1;
  /** BCP 47, e.g. "de-CH". */
  language: string;
  /** IANA zone, e.g. "Europe/Zurich". */
  timezone: string;
  /** ISO 3166 code of the home country or region, or "" when not given. */
  homeRegion: string;
  /** Region code (ISO 3166 or "GLOBAL") -> 0..1 */
  geographicInterests: Record<string, number>;
  /** Interest key (see INTEREST_KEYS) -> 0..1 */
  topicInterests: Record<string, number>;
  edition: { readingTimeMinutes: number; preferredDeliveryTime: string; discoveryRatio: number; depth: Depth };
  follows: { topics: string[]; authors: string[]; publishers: string[] };
  recurringSections: string[];
  behaviouralPersonalisation: boolean;
  readingHistory: boolean;
  /** "done" after onboarding, "skipped" if the reader chose to read without it. */
  onboarding: 'new' | 'done' | 'skipped';
  updatedAt?: string;
}

export const INTEREST_KEYS: { key: string; label: string }[] = [
  { key: 'politics', label: 'Politics' },
  { key: 'economy', label: 'Economy' },
  { key: 'technology', label: 'Technology' },
  { key: 'science', label: 'Science' },
  { key: 'society', label: 'Society' },
  { key: 'environment', label: 'Climate and environment' },
  { key: 'crises', label: 'Crises and conflicts' },
  { key: 'culture', label: 'Culture' },
  { key: 'travel', label: 'Travel' },
];
export const RECURRING: { key: string; label: string }[] = [
  { key: 'magazine', label: 'Magazine feature' },
  { key: 'good_news', label: 'Good News' },
  { key: 'editorial_outlook', label: 'Editorial outlook' },
  { key: 'random', label: 'Discovery of the day' },
];
export const REGIONS: { code: string; label: string }[] = [
  { code: 'CH', label: 'Switzerland' }, { code: 'DE', label: 'Germany' }, { code: 'AT', label: 'Austria' },
  { code: 'FR', label: 'France' }, { code: 'IT', label: 'Italy' }, { code: 'PE', label: 'Peru' },
  { code: 'US', label: 'United States' }, { code: 'EU', label: 'European Union' }, { code: 'GLOBAL', label: 'The world' },
];

const KEY = 'prismunfold.profile.v1';
const SAVED = 'prismunfold.saved.v1';
const HISTORY = 'prismunfold.history.v1';
const LEGACY = 'prismunfold.preferences.v1';
const MAX_LIST = 200;

export function defaultProfile(): ReaderProfile {
  return {
    version: 1, language: 'de-CH', timezone: 'Europe/Zurich', homeRegion: '',
    geographicInterests: {}, topicInterests: {},
    edition: { readingTimeMinutes: 15, preferredDeliveryTime: '07:00', discoveryRatio: 0.2, depth: 'standard' },
    follows: { topics: [], authors: [], publishers: [] },
    recurringSections: ['magazine', 'good_news', 'editorial_outlook'],
    behaviouralPersonalisation: false, readingHistory: false, onboarding: 'new',
  };
}

const clamp = (v: unknown, lo: number, hi: number, fallback: number): number =>
  typeof v === 'number' && Number.isFinite(v) ? Math.min(hi, Math.max(lo, v)) : fallback;
const code = (v: unknown): v is string => typeof v === 'string' && /^[A-Za-z0-9_-]{1,40}$/.test(v);
const weights = (v: unknown): Record<string, number> => {
  const out: Record<string, number> = {};
  if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
    for (const [k, w] of Object.entries(v).slice(0, 60)) if (code(k)) out[k] = clamp(w, 0, 1, 0);
  }
  return out;
};
const ids = (v: unknown): string[] =>
  Array.isArray(v) ? [...new Set(v.filter((x): x is string => typeof x === 'string' && x.length > 0 && x.length <= 160))].slice(0, MAX_LIST) : [];

/** Never throws; anything unreadable falls back to defaults. */
export function parseProfile(text: string | null): ReaderProfile | undefined {
  if (!text) return undefined;
  let raw: unknown;
  try { raw = JSON.parse(text); } catch { return undefined; }
  if (typeof raw !== 'object' || raw === null) return undefined;
  const r = raw as Record<string, unknown>;
  const d = defaultProfile();
  const e = (typeof r['edition'] === 'object' && r['edition'] !== null ? r['edition'] : {}) as Record<string, unknown>;
  const f = (typeof r['follows'] === 'object' && r['follows'] !== null ? r['follows'] : {}) as Record<string, unknown>;
  const depth = e['depth'];
  return {
    version: 1,
    language: typeof r['language'] === 'string' && /^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$/.test(r['language']) ? r['language'] : d.language,
    timezone: typeof r['timezone'] === 'string' && /^[A-Za-z_]+(\/[A-Za-z0-9_+-]+)*$/.test(r['timezone']) ? r['timezone'] : d.timezone,
    homeRegion: code(r['homeRegion']) ? r['homeRegion'] : '',
    geographicInterests: weights(r['geographicInterests']),
    topicInterests: weights(r['topicInterests']),
    edition: {
      readingTimeMinutes: Math.round(clamp(e['readingTimeMinutes'], 3, 90, d.edition.readingTimeMinutes)),
      preferredDeliveryTime: typeof e['preferredDeliveryTime'] === 'string' && /^([01]\d|2[0-3]):[0-5]\d$/.test(e['preferredDeliveryTime']) ? e['preferredDeliveryTime'] : d.edition.preferredDeliveryTime,
      discoveryRatio: clamp(e['discoveryRatio'], 0, 0.5, d.edition.discoveryRatio),
      depth: depth === 'brief' || depth === 'deep' || depth === 'standard' ? depth : 'standard',
    },
    follows: { topics: ids(f['topics']), authors: ids(f['authors']), publishers: ids(f['publishers']) },
    recurringSections: ids(r['recurringSections']).filter((k) => RECURRING.some((x) => x.key === k)),
    behaviouralPersonalisation: r['behaviouralPersonalisation'] === true,
    readingHistory: r['readingHistory'] === true,
    onboarding: r['onboarding'] === 'done' || r['onboarding'] === 'skipped' ? r['onboarding'] : 'new',
    updatedAt: typeof r['updatedAt'] === 'string' ? r['updatedAt'].slice(0, 40) : undefined,
  };
}

/** 0.2 preferences (languages/regions/sections) become a profile once. */
export function migrateLegacy(prefs: Preferences): ReaderProfile | undefined {
  if (!prefs.languages.length && !prefs.regions.length && !prefs.sections.length) return undefined;
  const p = defaultProfile();
  if (prefs.languages[0]) p.language = prefs.languages[0];
  for (const r of prefs.regions) if (code(r)) p.geographicInterests[r.toUpperCase()] = 1;
  for (const s of prefs.sections) if (code(s)) p.topicInterests[s] = 0.8;
  p.onboarding = 'done';
  return p;
}

function storage(): Storage | undefined {
  try { return globalThis.localStorage ?? undefined; } catch { return undefined; }
}

export function loadProfile(): ReaderProfile {
  const store = storage();
  try {
    const stored = parseProfile(store?.getItem(KEY) ?? null);
    if (stored) return stored;
    const migrated = migrateLegacy(parsePrefs(store?.getItem(LEGACY) ?? null));
    if (migrated) { saveProfile(migrated); return migrated; }
  } catch { /* storage blocked */ }
  return defaultProfile();
}

export function saveProfile(p: ReaderProfile): boolean {
  try {
    storage()?.setItem(KEY, JSON.stringify({ ...p, updatedAt: new Date().toISOString() }));
    if (!p.readingHistory) storage()?.removeItem(HISTORY);
    return !!storage();
  } catch { return false; }
}

/** Removes the profile, follows, saved articles and history from this device. */
export function resetAll(): void {
  for (const key of [KEY, SAVED, HISTORY, LEGACY]) {
    try { storage()?.removeItem(key); } catch { /* ignore */ }
  }
}

export const isPersonal = (p: ReaderProfile): boolean =>
  p.onboarding === 'done' && (Object.keys(p.topicInterests).length + Object.keys(p.geographicInterests).length
    + p.follows.topics.length + p.follows.authors.length + p.follows.publishers.length > 0);

// --- Saved articles and reading history (device-local) ---

export interface SavedItem { id: string; title: string; href: string; savedAt: string }

function readList<T>(key: string, check: (x: unknown) => x is T): T[] {
  try {
    const raw: unknown = JSON.parse(storage()?.getItem(key) ?? '[]');
    return Array.isArray(raw) ? raw.filter(check).slice(0, MAX_LIST) : [];
  } catch { return []; }
}
const isSaved = (x: unknown): x is SavedItem => typeof x === 'object' && x !== null
  && typeof (x as SavedItem).id === 'string' && typeof (x as SavedItem).title === 'string'
  && typeof (x as SavedItem).href === 'string' && (x as SavedItem).href.startsWith('/');

export const savedItems = (): SavedItem[] => readList(SAVED, isSaved);
export const isSavedItem = (id: string): boolean => savedItems().some((s) => s.id === id);

export function toggleSaved(item: Omit<SavedItem, 'savedAt'>): boolean {
  const items = savedItems();
  const exists = items.some((s) => s.id === item.id);
  const next = exists ? items.filter((s) => s.id !== item.id) : [{ ...item, savedAt: new Date().toISOString() }, ...items].slice(0, MAX_LIST);
  try { storage()?.setItem(SAVED, JSON.stringify(next)); } catch { /* ignore */ }
  return !exists;
}

export function history(): string[] {
  return readList(HISTORY, (x): x is string => typeof x === 'string');
}

/** Records a read article only when the reader enabled reading history. */
export function recordRead(id: string, p: ReaderProfile = loadProfile()): void {
  if (!p.readingHistory) return;
  const next = [id, ...history().filter((x) => x !== id)].slice(0, MAX_LIST);
  try { storage()?.setItem(HISTORY, JSON.stringify(next)); } catch { /* ignore */ }
}

export function clearHistory(): void {
  try { storage()?.removeItem(HISTORY); } catch { /* ignore */ }
}

export function toggleFollow(kind: keyof ReaderProfile['follows'], value: string): boolean {
  const p = loadProfile();
  const list = p.follows[kind];
  const following = !list.includes(value);
  p.follows[kind] = following ? [...list, value].slice(0, MAX_LIST) : list.filter((x) => x !== value);
  saveProfile(p);
  return following;
}
