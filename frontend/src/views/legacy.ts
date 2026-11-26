/**
 * Compatibility for 0.2 article URLs /morgenbriefing/{date}/artikel/{n}: the index
 * counted authored articles (Good News last), then the authored magazine, then
 * bulletin articles and bulletin magazines; without an authored edition, bulletin
 * articles came first. The same order is rebuilt from the daily edition.
 */
import type { ContentService } from '../content/content-service.ts';
import { paths } from '../lib/router.ts';
import type { DailyArticle, DailyEdition } from '../models-daily.ts';

export function legacyOrder(e: DailyEdition): DailyArticle[] {
  const bulletin = (a: DailyArticle) => a.provenance.provider === 'prism-data';
  const news = [...e.articles, ...e.goodNews];
  const authored = news.filter((a) => !bulletin(a));
  const authoredMagazine = e.magazine.filter((a) => !bulletin(a));
  const extras = news.filter(bulletin);
  const extraMagazines = e.magazine.filter(bulletin);
  return authored.length || authoredMagazine.length
    ? [...authored, ...authoredMagazine.slice(0, 1), ...extras, ...extraMagazines]
    : [...extras, ...extraMagazines];
}

export async function legacyArticlePath(svc: ContentService, date: string, index: number): Promise<string> {
  const edition = await svc.getDaily(date);
  const target = edition ? legacyOrder(edition)[index] : undefined;
  return target ? paths.article(target.articleId) : paths.edition(date);
}
