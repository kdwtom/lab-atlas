// Web data types — mirror of pipeline/schemas.py (web data section). Keep in sync.
// Unknown values are `null` and rendered as "정보 없음".

export type Univ = 'kaist' | 'snu' | 'postech' | 'unist' | 'gist' | 'dgist';
export type SourceKind =
  | 'faculty_page'
  | 'faculty_detail'
  | 'openalex_author'
  | 'openalex_works'
  | 'semantic_scholar'
  | 'homepage';
export type AuthorPosition = 'first' | 'middle' | 'last';
/** Field of a department: selection rules differ per field (pipeline config.DISCIPLINES) */
export type Discipline = 'life' | 'chem' | 'phys' | 'math' | 'cs';
export type ISODate = string; // YYYY-MM-DD

export interface Source {
  url: string;
  kind: SourceKind;
  retrieved_at: ISODate;
}

export interface YearKeywords {
  year: number;
  keywords: string[];
}

export interface Lab {
  id: string;
  univ: Univ;
  univ_name_ko: string;
  /** all departments listing the PI, joined with " · " (first = primary) */
  dept_name_ko: string;
  dept_codes: string[];
  disciplines: Discipline[];
  pi_name_ko: string | null;
  pi_name_en: string | null;
  position: string | null;
  lab_name: string | null;
  homepage_url: string | null;
  faculty_page_url: string;
  openalex_id: string;
  orcid: string | null;
  match_confidence: 'high' | 'medium';
  paper_count_5y: number;
  senior_paper_count_5y: number;
  keywords: string[];
  cluster_id: number | null;
  x: number | null;
  y: number | null;
  intro_ko: string | null;
  representative_paper_ids: string[];
  keyword_timeline: YearKeywords[];
  sources: Source[];
}

export interface PiRole {
  position: AuthorPosition;
  is_corresponding: boolean;
  /** PI authorship lists the lab's institution (or none); other papers are excluded from analysis */
  at_home_institution: boolean;
  /** counted toward the criterion under an alphabetical-author-order rule (mathematics, theory CS) */
  order_agnostic: boolean;
}

export interface Topic {
  id: string;
  name: string;
  score: number;
  subfield: string | null;
  field: string | null;
  domain: string | null;
}

export interface PaperSummary {
  one_line: string;
  background: string;
  methods: string;
  findings: string;
  significance: string;
}

export interface Paper {
  id: string;
  lab_ids: string[];
  title: string;
  year: number;
  venue: string | null;
  doi: string | null;
  cited_by_count: number;
  type: string;
  pi_roles: Record<string, PiRole>;
  has_abstract: boolean;
  has_tldr: boolean;
  topics: Topic[];
  summary_ko: PaperSummary | null;
  openalex_url: string;
  retrieved_at: ISODate;
}

export interface Edge {
  source: string;
  target: string;
  type: 'similarity' | 'coauthor';
  weight: number;
  reasons: string[];
  paper_ids: string[];
  /** the two labs belong to different fields */
  cross: boolean;
}

export interface Cluster {
  id: number;
  label_ko: string;
  keywords: string[];
  size: number;
}

export interface Meta {
  generated_at: ISODate;
  data_retrieved_at: ISODate;
  window_years: [number, number];
  min_senior_papers: number;
  louvain_resolution: number | null;
  louvain_seed: number | null;
  similarity_k: number | null;
  similarity_threshold: number | null;
  counts: {
    labs: number;
    papers: number;
    edges_similarity: number;
    edges_coauthor: number;
  };
  /** Hand-written Korean content coverage; anything missing is shown as "정보 없음" */
  summary_coverage: {
    representative_papers: number;
    papers_with_summary: number;
    labs: number;
    labs_with_intro: number;
  } | null;
  /** Papers removed after namesake review (pipeline/curation/excluded_papers.csv) */
  excluded_namesake_papers: number;
  departments: DepartmentInfo[];
  /** field -> selection rule, in Korean */
  rules: Partial<Record<Discipline, string>>;
}

export interface DepartmentInfo {
  code: string;
  univ: Univ;
  univ_name_ko: string;
  name_ko: string;
  discipline: Discipline;
  faculty_list_url: string;
  labs: number;
}
