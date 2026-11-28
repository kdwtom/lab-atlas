import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fromKeyboard } from './fixtures/legacy-search';
const baseline = JSON.parse(readFileSync(new URL('../../../docs/search/baseline-results.json', import.meta.url), 'utf8'));
const inventory = JSON.parse(readFileSync(new URL('../../../docs/search/benchmark.json', import.meta.url), 'utf8'));
describe('frozen baseline provenance', () => {
  it('has all 50 cases and unchanged source files', () => {
    expect(baseline.results).toHaveLength(50);
    expect(inventory.cases).toHaveLength(50);
    for (const [file, digest] of Object.entries(inventory.files)) {
      expect(createHash('sha256').update(readFileSync(new URL(`../../public/data/${file}`, import.meta.url))).digest('hex')).toBe(digest);
    }
  });
  it('preserves the two-set keyboard converter baseline', () => {
    expect(fromKeyboard('ausdur')).toBe('면역');
    expect(fromKeyboard('qq')).toBeNull();
  });
});
