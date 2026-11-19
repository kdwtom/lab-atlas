import type { Lab, Paper } from '../types/data';

/** English research term -> Korean renderings (pipeline/curation/search_terms_ko.json, written with the Claude API). */
export type Terms = Record<string, string[]>;

// ------------------------------------------------------------------ Korean typed on an English keyboard layout
// "aus dur" -> "면역": the standard two-set (두벌식) layout, composed into syllables.
const KEY: Record<string, string> = {
  q: 'ㅂ', w: 'ㅈ', e: 'ㄷ', r: 'ㄱ', t: 'ㅅ', y: 'ㅛ', u: 'ㅕ', i: 'ㅑ', o: 'ㅐ', p: 'ㅔ',
  a: 'ㅁ', s: 'ㄴ', d: 'ㅇ', f: 'ㄹ', g: 'ㅎ', h: 'ㅗ', j: 'ㅓ', k: 'ㅏ', l: 'ㅣ',
  z: 'ㅋ', x: 'ㅌ', c: 'ㅊ', v: 'ㅍ', b: 'ㅠ', n: 'ㅜ', m: 'ㅡ',
  Q: 'ㅃ', W: 'ㅉ', E: 'ㄸ', R: 'ㄲ', T: 'ㅆ', O: 'ㅒ', P: 'ㅖ',
};
const CHO = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ';
const JUNG = 'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ';
const JONG = ['', 'ㄱ', 'ㄲ', 'ㄳ', 'ㄴ', 'ㄵ', 'ㄶ', 'ㄷ', 'ㄹ', 'ㄺ', 'ㄻ', 'ㄼ', 'ㄽ', 'ㄾ', 'ㄿ', 'ㅀ', 'ㅁ', 'ㅂ', 'ㅄ', 'ㅅ',
  'ㅆ', 'ㅇ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'];
const VOWEL_PAIR: Record<string, string> = { ㅗㅏ: 'ㅘ', ㅗㅐ: 'ㅙ', ㅗㅣ: 'ㅚ', ㅜㅓ: 'ㅝ', ㅜㅔ: 'ㅞ', ㅜㅣ: 'ㅟ', ㅡㅣ: 'ㅢ' };
const FINAL_PAIR: Record<string, string> = {
  ㄱㅅ: 'ㄳ', ㄴㅈ: 'ㄵ', ㄴㅎ: 'ㄶ', ㄹㄱ: 'ㄺ', ㄹㅁ: 'ㄻ', ㄹㅂ: 'ㄼ', ㄹㅅ: 'ㄽ', ㄹㅌ: 'ㄾ', ㄹㅍ: 'ㄿ', ㄹㅎ: 'ㅀ', ㅂㅅ: 'ㅄ',
};
const isVowel = (c: string | undefined) => c !== undefined && JUNG.includes(c);
const isCons = (c: string | undefined) => c !== undefined && CHO.includes(c);

/** The Hangul a two-set keyboard would have produced, or null when the keys do not spell whole syllables. */
export function fromKeyboard(word: string): string | null {
  if (!/^[a-zA-Z]+$/.test(word)) return null;
  const j = [...word].map((ch) => KEY[ch] ?? KEY[ch.toLowerCase()]);
  let out = '';
  let i = 0;
  while (i < j.length) {
    const c = j[i];
    if (!isCons(c) || !isVowel(j[i + 1])) return null; // a syllable must start consonant + vowel
    let v = j[i + 1];
    i += 2;
    if (VOWEL_PAIR[v + j[i]]) v = VOWEL_PAIR[v + j[i++]];
    let jong = '';
    // a consonant closes this syllable unless a vowel follows it (then it opens the next one)
    if (isCons(j[i]) && JONG.includes(j[i]) && !isVowel(j[i + 1])) {
      jong = j[i++];
      if (isCons(j[i]) && FINAL_PAIR[jong + j[i]] && !isVowel(j[i + 1])) jong = FINAL_PAIR[jong + j[i++]];
    }
    out += String.fromCharCode(0xac00 + (CHO.indexOf(c) * 21 + JUNG.indexOf(v)) * 28 + JONG.indexOf(jong));
  }
  return out;
}

// ------------------------------------------------------------------ index
const norm = (s: string) => s.toLowerCase().normalize('NFC').replace(/[\s\-‐·_/,()]/g, '');
const HANGUL = /[가-힣]/;

type Field = 'name' | 'keyword' | 'cluster' | 'intro' | 'title';
const WEIGHT: Record<Field, number> = { name: 6, keyword: 4, cluster: 3, intro: 2, title: 1 };
const FIELD_KO: Record<Field, string> = { name: '이름', keyword: '키워드', cluster: '분야', intro: '소개', title: '논문' };

interface Entry {
  lab: Lab;
  names: string[];
  keywords: { en: string; ko: string[] }[];
  clusters: string[];
  intro: string;
  titles: string[];
}

export interface SearchIndex {
  entries: Entry[];
  /** single English words that are whole dictionary terms, lower-cased -> Korean renderings */
  wordKo: Map<string, string[]>;
}

export interface SearchHit {
  lab: Lab;
  score: number;
  /** why the lab matched, for the first query word, e.g. "키워드: Immunology (면역학)" */
  reason: string;
}

const TOPICS_PER_LAB = 12;

export function buildSearchIndex(labs: Lab[], papers: Paper[], terms: Terms, clusterLabel: (lab: Lab) => string[]): SearchIndex {
  const byLab = new Map<string, Paper[]>();
  for (const p of papers) for (const id of p.lab_ids) (byLab.get(id) ?? byLab.set(id, []).get(id)!).push(p);
  const entries = labs.map((lab) => {
    const ps = byLab.get(lab.id) ?? [];
    // the lab's own keywords first, then its papers' most frequent OpenAlex topics
    const counts = new Map<string, number>();
    for (const p of ps) for (const t of p.topics) counts.set(t.name, (counts.get(t.name) ?? 0) + 1);
    const topics = [...counts].sort((a, b) => b[1] - a[1]).slice(0, TOPICS_PER_LAB).map(([n]) => n);
    const kws = [...new Set([...lab.keywords, ...lab.keyword_timeline.flatMap((y) => y.keywords), ...topics])];
    return {
      lab,
      names: [lab.lab_name ?? '', lab.pi_name_ko ?? '', lab.pi_name_en ?? '', lab.dept_name_ko, lab.univ_name_ko].filter(Boolean),
      keywords: kws.map((en) => ({ en, ko: terms[en] ?? [] })),
      clusters: clusterLabel(lab),
      intro: lab.intro_ko ?? '',
      titles: ps.map((p) => p.title),
    };
  });
  const wordKo = new Map<string, string[]>();
  for (const [en, ko] of Object.entries(terms)) {
    const w = en.toLowerCase().replace(/\b(advanced|research|studies|techniques|applications|and)\b/g, ' ').replace(/\s+/g, ' ').trim();
    if (/^[a-z0-9-]+$/.test(w) && ko.length) wordKo.set(w, [...new Set([...(wordKo.get(w) ?? []), ...ko])]);
  }
  return { entries, wordKo };
}

type Matcher = (text: string) => boolean;

/** Latin words match from a word start ("RNA" must not hit "internal"); Korean matches anywhere. */
function matcher(word: string): Matcher {
  if (/^[a-z0-9]+$/i.test(word)) {
    const re = new RegExp(`(?<![a-z0-9])${word}`, 'i');
    return (text) => re.test(text);
  }
  const n = norm(word);
  return (text) => norm(text).includes(n);
}

interface Variant { m: Matcher; shown: string }

/** One query word -> the ways it can match: as typed; for an English word that is a whole term in the dictionary
 * ("immunology" -> "면역학"), also its Korean renderings, so it reaches Korean intros; when `keyboard` is on, also
 * the Hangul it spells on a two-set keyboard. */
function variants(index: SearchIndex, word: string, keyboard: boolean): Variant[] {
  const out: Variant[] = [{ m: matcher(word), shown: word }];
  for (const ko of index.wordKo.get(word.toLowerCase()) ?? []) out.push({ m: matcher(ko), shown: ko });
  const kb = keyboard ? fromKeyboard(word) : null;
  if (kb) out.push({ m: matcher(kb), shown: kb });
  return out;
}

function bestHit(e: Entry, vs: Variant[]): { field: Field; detail: string; via: string } | null {
  for (const { m, shown } of vs) {
    const name = e.names.find(m);
    if (name) return { field: 'name', detail: name, via: shown };
    const korean = HANGUL.test(shown);
    for (const k of e.keywords) {
      if (m(k.en)) return { field: 'keyword', detail: k.ko[0] ? `${k.en} (${k.ko[0]})` : k.en, via: shown };
      const ko = korean ? k.ko.find(m) : undefined;
      if (ko) return { field: 'keyword', detail: `${k.en} (${ko})`, via: shown };
    }
    const cl = e.clusters.find(m);
    if (cl) return { field: 'cluster', detail: cl, via: shown };
    if (m(e.intro)) return { field: 'intro', detail: '', via: shown };
    const title = e.titles.find(m);
    if (title) return { field: 'title', detail: title, via: shown };
  }
  return null;
}

/** Every word must match somewhere; the score adds each word's best field. */
function run(index: SearchIndex, words: string[], keyboard: boolean, note = ''): SearchHit[] {
  const vs = words.map((w) => variants(index, w, keyboard));
  const hits: SearchHit[] = [];
  for (const e of index.entries) {
    let score = 0;
    let reason = '';
    let ok = true;
    for (let i = 0; i < words.length; i++) {
      const h = bestHit(e, vs[i]);
      if (!h) { ok = false; break; }
      score += WEIGHT[h.field];
      if (!reason) {
        const via = h.via !== words[i] && !note ? `‘${words[i]}’→‘${h.via}’ · ` : '';
        reason = `${note}${via}${FIELD_KO[h.field]}${h.detail ? `: ${h.detail}` : ''}`;
      }
    }
    if (ok) hits.push({ lab: e.lab, score, reason });
  }
  return hits.sort((a, b) => b.score - a.score || b.lab.paper_count_5y - a.lab.paper_count_5y);
}

export function searchLabs(index: SearchIndex, query: string): SearchHit[] {
  const words = query.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return [];
  const asTyped = run(index, words, false);
  if (asTyped.length > 0) return asTyped;
  // nothing as typed: maybe Korean typed in English mode. Try the whole query as one word first ("aus dur" and
  // "ausdur" both -> "면역"), then word by word
  const joined = words.every((w) => /^[a-z]+$/i.test(w)) ? fromKeyboard(words.join('')) : null;
  if (joined) {
    const hits = run(index, [joined], false, `‘${words.join(' ')}’→‘${joined}’ · `);
    if (hits.length > 0) return hits;
  }
  return run(index, words, true);
}
