/**
 * Frontmatter parsing wrapper.
 *
 * gray-matter@4 binds js-yaml's `safeLoad` at import time. That API was removed
 * in js-yaml@4 (which a pnpm override pins repo-wide for the security fix), so
 * the default gray-matter engine throws "Function yaml.safeLoad is removed".
 * Supply a js-yaml-4 engine (`load`/`dump`) so frontmatter parsing works without
 * downgrading js-yaml. Use this everywhere instead of calling gray-matter directly.
 */
import matter from "gray-matter";
import yaml from "js-yaml";

const engines = {
  yaml: {
    parse: (input: string) => (yaml.load(input) as object) ?? {},
    stringify: (obj: object) => yaml.dump(obj),
  },
};

export function parseMatter(content: string): matter.GrayMatterFile<string> {
  return matter(content, { engines });
}
