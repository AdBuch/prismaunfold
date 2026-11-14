/**
 * Reader preferences. They live in this browser only and are never sent anywhere:
 * the edition is the same file for every reader and is filtered on the device.
 *
 * An empty list means "no restriction" for that dimension.
 */
export interface Preferences {
  languages: string[];
  regions: string[];
  sections: string[];
}

export interface Filterable {
  language?: string;
  regions?: string[];
  section: string;
}

const KEY = 'prismunfold.preferences.v1';
/** Stories outside the reader's selection that are still shown, so no edition becomes a bubble. */
export const OUTSIDE_LIMIT = 3;

export const emptyPrefs = (): Preferences => ({ languages: [], regions: [], sections: [] });

const strings = (v: unknown): string[] =>
  Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string' && x.length <= 80).slice(0, 50) : [];

export function parsePrefs(text: string | null): Preferences {
  if (!text) return emptyPrefs();
  try {
    const raw: unknown = JSON.parse(text);
    if (typeof raw !== 'object' || raw === null) return emptyPrefs();
    const r = raw as Record<string, unknown>;
    return { languages: strings(r['languages']), regions: strings(r['regions']), sections: strings(r['sections']) };
  } catch {
    return emptyPrefs();
  }
}

/** Storage can be missing or throw (private mode, blocked cookies); preferences then stay empty. */
export function loadPrefs(): Preferences {
  try {
    return parsePrefs(globalThis.localStorage?.getItem(KEY) ?? null);
  } catch {
    return emptyPrefs();
  }
}

export function savePrefs(prefs: Preferences): boolean {
  try {
    globalThis.localStorage?.setItem(KEY, JSON.stringify(prefs));
    return true;
  } catch {
    return false;
  }
}

export const hasPrefs = (p: Preferences): boolean => p.languages.length + p.regions.length + p.sections.length > 0;

export function matches(prefs: Preferences, item: Filterable): boolean {
  if (prefs.languages.length && item.language && !prefs.languages.includes(item.language)) return false;
  if (prefs.sections.length && !prefs.sections.includes(item.section)) return false;
  if (prefs.regions.length) {
    const regions = item.regions ?? [];
    // An item without a region is not tied to a place, so a region filter does not hide it.
    if (regions.length && !regions.some((r) => prefs.regions.includes(r))) return false;
  }
  return true;
}

/**
 * Split items into the reader's selection and the rest, keeping edition order.
 * The first item (the lead) always stays in the selection: the most important
 * story of the day is shown to everyone.
 */
export function applyPrefs<T extends Filterable>(items: T[], prefs: Preferences): { mine: T[]; outside: T[] } {
  if (!hasPrefs(prefs)) return { mine: items, outside: [] };
  const mine: T[] = [];
  const outside: T[] = [];
  items.forEach((item, i) => (i === 0 || matches(prefs, item) ? mine : outside).push(item));
  return { mine, outside };
}
