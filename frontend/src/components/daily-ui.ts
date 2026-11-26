/** Building blocks for canonical daily articles: teasers, images with rights, sources, labels. */
import { paths, slugify } from '../lib/router.ts';
import { formatMedium, html, type Raw } from '../lib/util.ts';
import type { DailyArticle, DailyImage, DailySource } from '../models-daily.ts';
import { runtime } from '../runtime.ts';

export const PROVIDER_LABEL: Record<string, string> = {
  codex: 'Codex · AI editorial worker',
  claude: 'Claude · AI editorial worker',
  mistral: 'Mistral · AI editorial worker',
  goose: 'Local model · AI editorial worker',
  chatgpt: 'ChatGPT · AI-curated bulletin',
  'prism-data': 'ChatGPT bulletin (prism-data) · AI-curated',
  rss: 'Original publisher',
  desk: 'PrismUnfold feed desk · extractive',
};
export const providerLabel = (p: string): string => PROVIDER_LABEL[p] ?? `${p} · contributor`;

/** Reader wording for source access (accessibility of a link, never truth of a claim). */
export const ACCESS_LABEL: Record<string, string> = {
  reachable: 'link opens',
  restricted: 'access restricted (paywall or blocked)',
  missing: 'link not found',
  rate_limited: 'not checked: publisher rate limit',
  unavailable: 'temporarily unavailable',
  timeout: 'did not answer in time',
  dns_failure: 'address not reachable',
  unsafe: 'not opened: unsafe address',
  unknown: 'not checked',
};

const IMAGE_ORIGIN: Record<string, string> = {
  publisher: 'Publisher image', wikimedia_commons: 'Wikimedia Commons', official: 'Official image',
  licensed_photo: 'Licensed photograph', chart: 'Chart', ai_illustration: 'AI-generated illustration',
};

/** Only images whose rights allow display are rendered; the article never depends on one. */
export function displayable(img: DailyImage): boolean {
  if (!img.display || !img.url || !img.credit) return false;
  if (/^https:\/\//i.test(img.url)) return true;
  return runtime.demo && img.url.startsWith('data:image/svg+xml');
}

export function leadImage(a: DailyArticle): DailyImage | undefined {
  return a.images.find(displayable);
}

export function dailyFigure(img: DailyImage, opts: { wide?: boolean; ratio?: string } = {}): Raw {
  if (!displayable(img) || !img.url) return html``;
  const ai = img.origin === 'ai_illustration';
  return html`<figure class="figure figure--photo${opts.wide ? ' figure--wide' : ''}${ai ? ' figure--ai' : ''}">
    <div class="figure__frame" style="aspect-ratio:${opts.ratio ?? '16 / 10'}"><img src="${img.url}" alt="${img.alt || img.caption}" loading="lazy" decoding="async" referrerpolicy="no-referrer"></div>
    <figcaption class="figcaption"><span>${ai ? html`<strong class="ai-label">AI illustration · not a photograph.</strong> ` : ''}${img.caption}</span>
      <span class="credit">${[img.credit, img.license, IMAGE_ORIGIN[img.origin] && !ai ? IMAGE_ORIGIN[img.origin] : ''].filter(Boolean).join(' · ')}${
        img.licenseUrl ? html` · <a href="${img.licenseUrl}" target="_blank" rel="noopener noreferrer">licence</a>` : ''}${
        img.sourceUrl ? html` · <a href="${img.sourceUrl}" target="_blank" rel="noopener noreferrer">source</a>` : ''}</span></figcaption>
  </figure>`;
}

export function sourceEntries(sources: DailySource[], idPrefix = 'src'): Raw {
  return html`<ol class="sources">${sources.map((s, i) => html`<li id="${idPrefix}-${i + 1}">
    <a href="${s.url}" target="_blank" rel="noopener noreferrer">${s.title}<span class="sr-only"> (opens in a new tab)</span></a>
    <span class="sources__meta">${[s.publisher, s.author, s.publishedAt ? formatMedium(s.publishedAt) : '', s.sourceType].filter(Boolean).join(' · ')}${
      s.access === 'paywalled' ? ' · paywall' : ''}${s.linkStatus ? html` · <span class="access access--${s.linkStatus}">${ACCESS_LABEL[s.linkStatus] ?? s.linkStatus}</span>` : ''}</span>
  </li>`)}</ol>`;
}

export function articleMarks(a: DailyArticle): Raw {
  return html`${a.reviewRequired ? html`<span class="mark mark--review_required">Needs review</span>` : ''}${
    a.corrections?.length ? html`<span class="mark mark--correction">Corrected</span>` : ''}${
    a.provenance.provider === 'prism-data' ? html`<span class="mark">AI-curated bulletin</span>` : ''}${
    a.coverage.length ? html`<span class="mark">${a.coverage.length + 1} contributors</span>` : ''}`;
}

const href = (a: DailyArticle) => paths.article(a.articleId);

export function leadTeaser(a: DailyArticle, why?: Raw): Raw {
  const img = leadImage(a);
  return html`<article class="lead${img ? '' : ' lead--text'}">
    ${img ? html`<a class="lead__media" href="${href(a)}" data-link tabindex="-1" aria-hidden="true">${dailyFigure(img, { ratio: '4 / 3' })}</a>` : ''}
    <p class="kicker">${a.section}</p>
    <h2 class="lead__title"${a.language ? html` lang="${a.language}"` : ''}><a href="${href(a)}" data-link>${a.headline}</a></h2>
    <p class="lead__dek">${a.summary ?? a.lead}</p>
    ${a.whyItMatters ? html`<p class="lead__why"><strong>Why it matters.</strong> ${a.whyItMatters}</p>` : ''}
    <p class="more"><a href="${href(a)}" data-link>Read and unfold</a> ${articleMarks(a)}</p>${why ?? ''}
  </article>`;
}

export function secondaryTeaser(a: DailyArticle, why?: Raw): Raw {
  return html`<article class="secondary">
    <p class="kicker">${a.section}</p>
    <h3 class="secondary__title"><a href="${href(a)}" data-link>${a.headline}</a></h3>
    <p class="secondary__dek">${a.lead}</p>${articleMarks(a)}${why ?? ''}
  </article>`;
}

export function itemTeaser(a: DailyArticle, why?: Raw): Raw {
  const img = leadImage(a);
  return html`<article class="item">
    ${img ? html`<a class="item__media" href="${href(a)}" data-link tabindex="-1" aria-hidden="true">${dailyFigure(img, { ratio: '3 / 2' })}</a>` : ''}
    <div class="item__text"><h3 class="item__title"><a href="${href(a)}" data-link>${a.headline}</a></h3>
    <p class="item__dek">${a.lead}</p>${articleMarks(a)}${why ?? ''}</div>
  </article>`;
}

export function featureTeaser(a: DailyArticle): Raw {
  const img = leadImage(a);
  return html`<section class="feature${img ? '' : ' feature--text'}" aria-labelledby="feature-heading">
    ${img ? html`<a class="feature__media" href="${href(a)}" data-link tabindex="-1" aria-hidden="true">${dailyFigure(img, { ratio: '5 / 4' })}</a>` : ''}
    <div class="feature__text">
      <p class="kicker kicker--light">Magazine · Background</p>
      <h2 id="feature-heading" class="feature__title"><a href="${href(a)}" data-link>${a.headline}</a></h2>
      <p class="feature__dek">${a.lead}</p>
      <p class="feature__meta">${providerLabel(a.provenance.provider)}</p>
      <a class="btn btn--light" href="${href(a)}" data-link>Read the feature</a>
    </div>
  </section>`;
}

export const authorHref = (name: string): string => paths.author(slugify(name));
