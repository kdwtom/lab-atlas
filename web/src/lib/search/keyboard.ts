// Existing two-set keyboard converter, preserved from the baseline.
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
