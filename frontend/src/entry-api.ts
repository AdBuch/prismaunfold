// Production entry: real stories from the pipeline's JSON API. No fixture content is bundled.
import { ApiContentService } from './content/api-service.ts';
import { boot } from './main.ts';

boot(new ApiContentService(), { demo: false });
