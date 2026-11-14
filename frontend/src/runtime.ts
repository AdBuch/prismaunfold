import type { Section } from './models.ts';

/**
 * Process-wide state set once at boot and refreshed when site info loads.
 * `demo` switches the fictional-content banner and wording on.
 */
export const runtime: { demo: boolean; sections: Section[] } = { demo: false, sections: [] };
