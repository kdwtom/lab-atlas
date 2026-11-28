import data from './concepts.data.json';
import type { ConceptDictionary } from './types';
import { fold, stableCompare } from './normalize';
interface Alias { id: string; re: RegExp; length: number; guard?: readonly string[] }
export interface Mention { id: string; start: number; end: number }
const compiled = new WeakMap<ConceptDictionary, readonly Alias[]>();
const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
export const dictionary = data as ConceptDictionary;
export function compileConcepts(dict: ConceptDictionary): ConceptDictionary {
  if (compiled.has(dict)) return dict;
  const aliases: Alias[] = []; const owners = new Map<string,string>(); const ids = new Set<string>();
  for (const c of dict.concepts) {
    if (c.review.status !== 'approved') continue;
    if (ids.has(c.id) || !c.review.reviewer || !c.review.date) throw new Error(`Invalid concept review/id: ${c.id}`);
    ids.add(c.id);
    for (const a of c.aliases) {
      const text = fold(a.text).trim();
      if (!text || !/[\p{L}\p{N}]/u.test(text)) throw new Error(`Empty concept alias: ${c.id}`);
      const key = text.replace(/[-‐‑–—\s]+/g,' ');
      const previous = owners.get(key);
      if (previous && previous !== c.id) throw new Error(`Ambiguous concept alias: ${text}`);
      owners.set(key,c.id);
      const korean = /[가-힣]/.test(text);
      const body = a.hangulSegments ? a.hangulSegments.map((s) => escape(fold(s))).join('[ \\t]*') : text.split(/[-‐‑–—\s]+/).map(escape).join('[\\s\\-‐‑–—]+');
      const pattern = korean ? body : `(?<![\\p{L}\\p{N}])${body}(?![\\p{L}\\p{N}])`;
      aliases.push({id:c.id,re:new RegExp(pattern,'gu'),length:text.length,guard:a.guard?.anyConceptIds});
    }
  }
  compiled.set(dict, aliases.sort((a,b) => b.length-a.length || stableCompare(a.id,b.id)));
  return dict;
}
export function recognizeConcepts(text: string, dict: ConceptDictionary): Mention[] {
  compileConcepts(dict); const value = fold(text); const candidates: (Mention & {guard?:readonly string[]})[] = [];
  for (const a of compiled.get(dict)!) {
    a.re.lastIndex = 0;
    for (const m of value.matchAll(a.re)) candidates.push({id:a.id,start:m.index!,end:m.index!+m[0].length,guard:a.guard});
  }
  const unambiguous = new Set(candidates.filter((c) => !c.guard).map((c) => c.id));
  candidates.sort((a,b) => (b.end-b.start)-(a.end-a.start) || a.start-b.start || stableCompare(a.id,b.id));
  const selected: Mention[] = [];
  for (const c of candidates) {
    if (c.guard && !c.guard.some((id) => unambiguous.has(id))) continue;
    if (!selected.some((s) => c.start < s.end && c.end > s.start)) selected.push({id:c.id,start:c.start,end:c.end});
  }
  return selected.sort((a,b) => a.start-b.start);
}
export function getConceptLabel(id: string, dict = dictionary): string {
  const c = dict.concepts.find((x) => x.id === id);
  return c ? `${c.labelKo} ↔ ${c.labelEn}` : id;
}
