/**
 * Cross-edition views (World, Magazine, Topics, Voices) are compositions over the same
 * canonical articles. Until the pipeline exports topic, author and magazine indexes
 * (docs/PIPELINE_INTERFACE.md), they are assembled from the most recent editions.
 */
import { allArticles, type DailyArticle, type DailyEdition } from '../models-daily.ts';
import type { ContentService } from './content-service.ts';

export const RECENT_EDITIONS = 14;

export async function recentDaily(svc: ContentService, limit = RECENT_EDITIONS, filter?: (e: { magazineCount: number }) => boolean): Promise<DailyEdition[]> {
  const index = (await svc.listDaily()).filter((e) => !filter || filter(e)).slice(0, limit);
  const editions = await Promise.all(index.map((e) => svc.getDaily(e.date).catch(() => undefined)));
  return editions.filter((e): e is DailyEdition => !!e);
}

export interface Placed { article: DailyArticle; date: string }

export function placed(editions: DailyEdition[]): Placed[] {
  return editions.flatMap((e) => allArticles(e).map((article) => ({ article, date: e.date })));
}

export interface TopicSummary { slug: string; count: number; first: string; last: string; latest: DailyArticle; sections: string[] }

export function topicsOf(items: Placed[]): TopicSummary[] {
  const map = new Map<string, Placed[]>();
  for (const p of items) if (p.article.topic) map.set(p.article.topic, [...(map.get(p.article.topic) ?? []), p]);
  return [...map].map(([slug, list]) => {
    const dates = list.map((p) => p.date).sort();
    const latest = [...list].sort((a, b) => b.date.localeCompare(a.date))[0] as Placed;
    return { slug, count: list.length, first: dates[0] ?? '', last: dates[dates.length - 1] ?? '', latest: latest.article,
      sections: [...new Set(list.map((p) => p.article.section))] };
  }).sort((a, b) => b.last.localeCompare(a.last) || b.count - a.count || a.slug.localeCompare(b.slug));
}

export const humanize = (slug: string): string => {
  const text = slug.replace(/[-_]+/g, ' ').trim();
  return text ? text[0]!.toUpperCase() + text.slice(1) : slug;
};

/** Same text once: background explanations are shown at dossier level, not repeated per article. */
export function uniqueBy<T>(items: T[], key: (t: T) => string): T[] {
  const seen = new Set<string>();
  return items.filter((i) => { const k = key(i).toLowerCase().replace(/\s+/g, ' ').trim(); return !seen.has(k) && !!seen.add(k); });
}
