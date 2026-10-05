import type { Lab, Univ } from '../types/data';

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
