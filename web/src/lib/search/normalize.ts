import type { NormalizedText } from './types';
export const fold = (s: string) => s.normalize('NFKC').toLowerCase();
export const nameKey = (s: string) => fold(s).replace(/[-‐‑–—]/g, ' ').replace(/\s+/g, ' ').trim();
export function exactName(a: string, b: string): boolean {
  const x = nameKey(a); const y = nameKey(b);
  if (x === y && x.length > 0) return true;
  return /^[가-힣\s]+$/.test(x) && /^[가-힣\s]+$/.test(y) && x.replace(/\s/g, '') === y.replace(/\s/g, '');
}
export function normalizeText(text: string): NormalizedText {
  const folded = fold(text).trim().replace(/\s+/g, ' ');
  const tokens: {text:string;segment:number}[] = [];
  let segment = 0; let end = 0;
  // Preserve C++/C# and Unicode letters. Only spaces/hyphens can bridge phrases.
  for (const m of folded.matchAll(/[\p{L}\p{N}]+(?:\+\+|#)?/gu)) {
    if (/[^\s\-‐‑–—]/u.test(folded.slice(end, m.index))) segment++;
    tokens.push({text:m[0],segment}); end = m.index! + m[0].length;
  }
  return {folded,tokens};
}
export function hasPhrase(text: NormalizedText, phrase: readonly string[]): boolean {
  return phrase.length > 0 && text.tokens.some((t,i) => t.text === phrase[0] && phrase.every((word,j) => text.tokens[i+j]?.text === word && text.tokens[i+j]?.segment === t.segment));
}
export const literalHit = (text: NormalizedText, word: string) => text.tokens.some((t) => /[가-힣]/.test(word) ? t.text.includes(word) : t.text === word);
export const stableCompare = (a: string, b: string) => a < b ? -1 : a > b ? 1 : 0;
