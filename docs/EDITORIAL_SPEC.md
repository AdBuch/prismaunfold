# Morgenbriefing Weltlage — canonical editorial specification

## Core configuration
- Daily at 07:00, Zürich time.
- German, Swiss spelling.
- Concise, factual, analytical, inspired by NZZ.
- Approximately 60% of the original editions.
- Prioritise new developments since the previous briefing.
- Primary sources, independent media, contrasting perspectives.
- Maximum twice per week per international topic, unless substantial developments occur.

## Editorial structure
1. Schweiz Politik
2. Schweiz Gesellschaft
3. Schweiz Regional — Zürich approximately every second day
4. Peru Politik
5. Peru Gesellschaft
6. Krisen- und Konfliktgebiete
7. Reisen — personalised to travel plans
8. International — geographical rotation
9. Wirtschaft, Technologie & Wissenschaft — included in several recent editions, not explicitly defined in the latest recurring prompt.

## Additional sections
- Vertiefung des Tages: independently researched magazine-style article about an important, underestimated topic, approximately 0.75–1 A4 page.
- Good News: one concrete positive development.
- Random des Tages: one surprising educational fact.
- Lagebild: four compact assessments — important, overrated, underreported and worth monitoring.

## Editorial principles
Rewrite and synthesise reporting rather than merely summarising individual websites. Distinguish verified facts, analysis, allegations and uncertainty. Link original documents and reporting. Avoid artificial political balance. Explain why developments matter. Omit insignificant updates rather than filling sections artificially.

The underlying objective is a personalised digital newspaper, not a news aggregator.

## Implementation boundary
Research, editorial selection, article writing and independent fact-checking are separate responsibilities, supported by persistent publication history. The Codex implementation combines research and writing in one structured invocation by default (a split research/writing mode is experimental); evidence checking, review and publication never call a model, and a scheduled 06:00/07:00 workflow exists (see EDITORIAL_WORKFLOW.md). Independent fact-checking, travel preferences, expanded source permissions and deterministic topic repetition/continental rotation are not yet implemented. A link check does not verify a claim. Do not present these gaps as completed. Travel preferences are private deployment configuration, not Git content. Editorial target supplied by project owner 2026-11-24; changes to the target belong here before implementation changes.
