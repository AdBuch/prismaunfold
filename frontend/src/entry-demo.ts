// Demo entry: fictional fixtures, clearly labelled. Built with PRISM_CONTENT=demo; used by the e2e tests.
import { FixtureContentService } from './content/fixture-service.ts';
import { boot } from './main.ts';

boot(new FixtureContentService(), { demo: true });
