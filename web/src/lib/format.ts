import type { Lab, Meta, Univ } from '../types/data';

export const NA = '정보 없음';

export const UNIV_ORDER: Univ[] = ['kaist', 'snu', 'postech', 'unist', 'gist', 'dgist'];
export const UNIV_LABEL: Record<Univ, string> = {
  kaist: 'KAIST',
  snu: '서울대',
  postech: 'POSTECH',
  unist: 'UNIST',
  gist: 'GIST',
  dgist: 'DGIST',
};

/** The GitHub Actions build sets VITE_REPO_URL to the repository; local builds fall back to a placeholder. */
const REPO_URL = (import.meta.env.VITE_REPO_URL as string | undefined) || 'https://github.com/OWNER/lab-atlas';
export const ISSUE_URL = `${REPO_URL}/issues/new`;

export function piName(lab: Lab): string {
  return lab.pi_name_ko ?? lab.pi_name_en ?? lab.openalex_id;
}

export function labTitle(lab: Lab): string {
  return lab.lab_name ?? `${piName(lab)} 연구실`;
}

export function affiliation(lab: Lab): string {
  return `${lab.univ_name_ko} ${lab.dept_name_ko}`;
}

const INTRO_UNAVAILABLE: Record<NonNullable<Lab['intro_unavailable']>, string> = {
  insufficient_papers: '소개 없음: 수집된 논문이 적어 연구 주제를 말하기 어렵습니다.',
  mixed_topics: '소개 없음: 논문 주제가 서로 동떨어져 있어 동명이인의 논문이 섞였을 수 있습니다.',
  wrong_field: '소개 없음: 수집된 논문이 학과 분야와 맞지 않아 다른 연구자의 프로필로 잘못 연결됐을 수 있습니다.',
};

/** The lab's intro, or why it has none; never implies anything about the lab's research output. */
export function introText(lab: Lab): string {
  if (lab.intro_ko) return lab.intro_ko;
  return lab.intro_unavailable ? INTRO_UNAVAILABLE[lab.intro_unavailable] : NA;
}

/**
 * Words instead of a cosine value: the value has no absolute meaning and its range differs per field, so the
 * cut-offs are per field (pipeline step08_analyze.similarity_band has the same rule).
 */
export function similarityBand(meta: Meta, weight: number, a: Lab, b: Lab): string {
  const threshold = meta.similarity_threshold;
  if (threshold !== null && weight < threshold) return '주제 거리가 있음';
  const group = a.disciplines[0] === b.disciplines[0] ? a.disciplines[0] : 'cross';
  const cuts = meta.similarity_bands?.[group] ?? meta.similarity_bands?.all;
  if (!cuts) return '가까움';
  if (weight >= cuts[1]) return '매우 가까움';
  return weight >= cuts[0] ? '가까움' : '비교적 가까움';
}

/**
 * Warning for labs whose vector rests on few papers. The audit (pipeline/output/similarity_audit.md) shows half of such
 * a lab's papers often fail to find the other half.
 */
export function neighbourCaution(...labs: Lab[]): string | null {
  const least = labs.reduce((a, b) => (b.vector_paper_count < a.vector_paper_count ? b : a));
  const n = least.vector_paper_count;
  if (n > 10) return null;
  const who = labs.length > 1 ? `${piName(least)} 연구실은 ` : '';
  return n <= 5
    ? `${who}논문 ${n}편으로 계산해 가까운 연구실 목록이 크게 달라질 수 있습니다.`
    : `${who}논문 ${n}편으로 계산해 가까운 연구실 목록이 달라질 수 있습니다.`;
}

export function or<T>(v: T | null | undefined, fallback: string = NA): T | string {
  return v === null || v === undefined || v === '' ? fallback : v;
}

export function fmtDate(iso: string): string {
  const [y, m, d] = iso.split('-');
  return `${y}년 ${Number(m)}월 ${Number(d)}일`;
}

export function doiHref(doi: string | null): string | null {
  if (!doi) return null;
  return doi.startsWith('http') ? doi : `https://doi.org/${doi}`;
}
