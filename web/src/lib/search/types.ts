import type { Cluster, Discipline, Lab, Paper, Univ } from '../../types/data';
export type Terms = Record<string, string[]>;
export interface SearchFilters { univs: ReadonlySet<Univ>; fields: ReadonlySet<Discipline>; clusters: ReadonlySet<number> }
export interface SearchDataset { version: string; labs: readonly Lab[]; papers: readonly Paper[]; clusters: readonly Cluster[]; legacyTerms: Readonly<Terms> }
export type SearchField = 'pi_name_ko' | 'pi_name_en' | 'lab_name' | 'university' | 'department' | 'keyword' | 'timeline_keyword' | 'intro' | 'paper_title' | 'paper_topic' | 'cluster' | 'subcluster' | 'translated_label';
export interface ConceptAlias { text: string; language: 'ko' | 'en' | 'scientific'; kind: 'phrase' | 'abbreviation'; hangulSegments?: readonly string[]; guard?: { anyConceptIds: readonly string[] } }
export interface SearchConcept { id: string; labelKo: string; labelEn: string; disciplines: readonly Discipline[]; aliases: readonly ConceptAlias[]; relatedIds: readonly string[]; sourceExamples: readonly { labId: string; field: SearchField; paperId?: string; text: string }[]; review: { status: 'draft' | 'approved'; reviewer: string | null; date: string | null; note: string } }
export interface ConceptDictionary { version: string; concepts: readonly SearchConcept[] }
export interface NormalizedText { folded: string; tokens: readonly { text: string; segment: number }[] }
export interface IndexedRecord { id: string; labIds: readonly string[]; field: SearchField; originalText: string; normalized: NormalizedText; conceptIds: ReadonlySet<string>; paperId?: string; year?: number; sourceRecordId?: string }
export interface SearchIndex { datasetVersion: string; dictionaryVersion: string; dictionary: ConceptDictionary; labs: ReadonlyMap<string, { lab: Lab; recordIds: readonly string[]; nameRecordIds: readonly string[] }>; names: ReadonlyMap<string,ReadonlySet<string>>; records: ReadonlyMap<string, IndexedRecord>; concepts: ReadonlyMap<string, ReadonlySet<string>>; tokens: ReadonlyMap<string, ReadonlySet<string>>; diagnostics: readonly string[]; buildMs: number }
export type QueryUnit = { id: string; kind: 'concept'; conceptId: string } | { id: string; kind: 'literal'; normalized: string } | { id: string; kind: 'phrase'; tokens: readonly string[] };
export interface ParsedQuery { raw: string; normalized: string; state: 'empty' | 'invalid' | 'ready'; units: readonly QueryUnit[]; key: string; notices: readonly string[]; literalGroups: readonly (readonly string[])[] }
export type EvidenceQuality = 'ordinary' | 'mixed_topics' | 'wrong_field';
export interface MatchEvidence { unitIds: readonly string[]; recordId: string; field: SearchField; conceptIds: readonly string[]; originalText: string; paperId?: string; sourceRecordId?: string; method: 'exact_name' | 'concept' | 'literal' | 'phrase' | 'legacy_translation'; quality: EvidenceQuality }
export type Caution = 'mixed_topics' | 'wrong_field' | 'limited_papers';
export interface LabMatch { labId: string; exactName: boolean; evidence: readonly MatchEvidence[]; coveredUnitIds: ReadonlySet<string>; requiresQuestionableEvidence: boolean; cautions: readonly Caution[] }
export interface SearchResult { labId: string; score: number; tier: 1 | 2 | 3 | 4 | 5; evidence: readonly MatchEvidence[]; coverage: 'single_record' | 'scattered'; cautions: readonly Caution[] }
export interface SearchResponse { query: ParsedQuery; eligibleLabIds: readonly string[]; results: readonly SearchResult[]; matchedIds: ReadonlySet<string>; total: number; unfilteredTotal?: number; correction?: { original: string; applied: string; kind: 'keyboard_layout' } }
export interface SearchOptions { keyboardCorrection?: boolean; includeUnfilteredCount?: boolean }
