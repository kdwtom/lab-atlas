import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import type { Lab } from '../types/data';
import { clusterPath, useAtlas } from '../data/DataContext';
import { useShortlist } from '../data/shortlist';
import StarButton from '../components/StarButton';
import { FieldChips } from '../components/LabPanel';
import { NA, affiliation, doiHref, introText, labTitle, neighbourCaution, piName, similarityBand } from '../lib/format';
import { FIELD_LABEL, FIELD_ORDER, type Mode } from '../lib/palette';
import { loadLabVectors, recommend, sharedTopics, topicProfiles, type LabVectors } from '../lib/recommend';

const MAX_COMPARE = 4;
const SEARCH_LIMIT = 12;
const REC_LIMIT = 12;
type RecField = 'all' | 'other' | (typeof FIELD_ORDER)[number];

const labLink = (id: string) => `/lab/${encodeURIComponent(id)}`;
function KeywordList({ items }: { items: string[] }) {
  if (items.length === 0) return <>{NA}</>;
  return <ul className="keyword-list">{items.map((k) => <li key={k}>{k}</li>)}</ul>;
}

const norm = (s: string) => s.toLowerCase().replace(/[\s\-‐·]/g, '');

/** Latin words match from a word start ("RNA" must not hit "internal"); Korean matches anywhere. */
function matcher(word: string): (text: string) => boolean {
  const w = word.toLowerCase();
  if (/^[a-z0-9]+$/.test(w)) {
    const re = new RegExp(`(?<![a-z0-9])${w}`, 'i');
    return (text) => re.test(text);
  }
  const n = norm(w);
  return (text) => norm(text).includes(n);
}

/** Plain text matching over names, intros, keywords and paper titles: every word must appear somewhere. */
function useSearch(query: string) {
  const { labs, papers } = useAtlas();
  const titles = useMemo(() => {
    const m = new Map<string, string[]>();
    for (const p of papers) for (const l of p.lab_ids) (m.get(l) ?? m.set(l, []).get(l)!).push(p.title);
    return m;
  }, [papers]);
  return useMemo(() => {
    const words = query.trim().split(/\s+/).filter(Boolean).map(matcher);
    if (words.length === 0) return [];
    const scored = labs.flatMap((lab) => {
      const names = `${labTitle(lab)} ${piName(lab)} ${lab.pi_name_en ?? ''} ${lab.dept_name_ko}`;
      const about = `${lab.intro_ko ?? ''} ${lab.keywords.join(' ')}`;
      const paperTitles = titles.get(lab.id) ?? [];
      let score = 0;
      let matchedTitle: string | undefined;
      for (const hit of words) {
        const title = paperTitles.find(hit);
        const inNames = hit(names);
        const inAbout = hit(about);
        if (!inNames && !inAbout && !title) return [];
        score += (inNames ? 3 : 0) + (inAbout ? 2 : 0) + (title ? 1 : 0);
        matchedTitle ??= !inNames && !inAbout ? title : undefined;
      }
      return [{ lab, score, matchedTitle }];
    });
    return scored.sort((a, b) => b.score - a.score || b.lab.paper_count_5y - a.lab.paper_count_5y);
  }, [query, labs, titles]);
}

function SearchSection() {
  const [query, setQuery] = useState('');
  const results = useSearch(query);
  return (
    <section aria-labelledby="find-title">
      <h2 id="find-title">관심사로 찾기</h2>
      <label className="sr-only" htmlFor="interest">관심 연구 주제</label>
      <input id="interest" className="interest" value={query} onChange={(e) => setQuery(e.target.value)}
             placeholder="예: 단백질 구조, graph neural network, 전고체 전지" autoComplete="off" />
      <p className="muted small">
        연구실 이름·소개·키워드·최근 논문 제목에서 글자가 일치하는 곳을 찾습니다. 뜻이 비슷한 말까지 찾지는 않으니, 한국어로 없으면 영어로도 찾아 보세요.
      </p>
      {query.trim() && (
        results.length === 0 ? <p className="empty">일치하는 연구실이 없습니다.</p> : (
          <>
            <p className="muted small" aria-live="polite">{results.length}곳 일치{results.length > SEARCH_LIMIT && `, 상위 ${SEARCH_LIMIT}곳 표시`}</p>
            <ul className="lab-rows">
              {results.slice(0, SEARCH_LIMIT).map(({ lab, matchedTitle }) => (
                <li key={lab.id}>
                  <StarButton id={lab.id} name={piName(lab)} compact />
                  <div>
                    <Link to={labLink(lab.id)} className="row-link">{piName(lab)}</Link>
                    <span className="muted small"> {affiliation(lab)}</span>
                    <p className="small row-intro">{matchedTitle ? `논문: ${matchedTitle}` : introText(lab)}</p>
                  </div>
                </li>
              ))}
            </ul>
          </>
        )
      )}
    </section>
  );
}

function Recommendations({ seeds, mode }: { seeds: Lab[]; mode: Mode }) {
  const atlas = useAtlas();
  const [vectors, setVectors] = useState<LabVectors | null>(null);
  const [failed, setFailed] = useState(false);
  const [field, setField] = useState<RecField>('all');

  useEffect(() => {
    let alive = true;
    loadLabVectors().then((v) => { if (alive) setVectors(v); }).catch(() => { if (alive) setFailed(true); });
    return () => { alive = false; };
  }, []);

  const profiles = useMemo(() => topicProfiles(atlas.papers), [atlas.papers]);
  const seedKey = seeds.map((s) => s.id).join('|');
  const ranked = useMemo(
    () => (vectors ? recommend(vectors, seeds.map((s) => s.id)) : []),
    [vectors, seedKey], // eslint-disable-line react-hooks/exhaustive-deps -- seeds are identified by their ids
  );
  const seedFields = new Set(seeds.flatMap((s) => s.disciplines));
  const rows = ranked.flatMap((r) => {
    const lab = atlas.labById.get(r.id);
    // mixed or mismatched paper lists make the lab's vector unreliable, so it is not recommended
    if (!lab || lab.intro_unavailable === 'mixed_topics' || lab.intro_unavailable === 'wrong_field') return [];
    const keep = field === 'all' || (field === 'other'
      ? !lab.disciplines.some((d) => seedFields.has(d))
      : lab.disciplines.includes(field));
    return keep ? [{ ...r, lab }] : [];
  }).slice(0, REC_LIMIT);

  return (
    <section aria-labelledby="rec-title">
      <h2 id="rec-title">비슷한 연구실 추천</h2>
      <p className="muted small">
        담은 연구실들의 논문 내용과 가까운 순서입니다. 연구실의 수준이나 평가가 아니라, 담은 곳과의 주제 거리만 나타냅니다.
      </p>
      <div className="chips" role="group" aria-label="추천 분야 필터">
        {(['all', 'other', ...FIELD_ORDER] as RecField[]).map((f) => (
          <button key={f} type="button" className="chip" aria-pressed={field === f} onClick={() => setField(f)}>
            {f === 'all' ? '전체' : f === 'other' ? '다른 분야만' : FIELD_LABEL[f]}
          </button>
        ))}
      </div>
      {failed && <p className="notice" role="alert">추천 데이터를 불러오지 못했습니다. 새로고침해 주세요.</p>}
      {!failed && !vectors && <p className="muted" role="status">추천을 계산하는 중…</p>}
      {vectors && rows.length === 0 && <p className="empty">이 조건에 맞는 연구실이 없습니다.</p>}
      <ol className="lab-rows">
        {rows.map(({ lab, nearestSeed, nearestSimilarity }) => {
          const seed = atlas.labById.get(nearestSeed);
          const topics = sharedTopics(profiles.get(lab.id), profiles.get(nearestSeed));
          const caution = seed ? neighbourCaution(lab, seed) : neighbourCaution(lab);
          return (
            <li key={lab.id}>
              <StarButton id={lab.id} name={piName(lab)} compact />
              <div>
                <Link to={labLink(lab.id)} className="row-link">{piName(lab)}</Link>
                <span className="muted small"> {affiliation(lab)}</span>
                <div className="chip-row"><FieldChips lab={lab} mode={mode} /></div>
                <p className="small row-intro">{introText(lab)}</p>
                <p className="muted small">
                  이유: 담은 연구실 중 {seed ? piName(seed) : NA}에 가장 가까움
                  {seed && `(${similarityBand(atlas.meta, nearestSimilarity, lab, seed)})`}
                  {topics.length > 0 && ` · 공통 주제: ${topics.join(', ')}`}
                </p>
                {caution && <p className="muted small">{caution}</p>}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function Compare({ labs, mode }: { labs: Lab[]; mode: Mode }) {
  const atlas = useAtlas();
  const between = (a: Lab, others: Lab[]) => {
    const parts = others.flatMap((b) => {
      const sim = atlas.neighbors(a.id, 'similarity').find((n) => n.lab.id === b.id);
      const co = atlas.neighbors(a.id, 'coauthor').find((n) => n.lab.id === b.id);
      if (!sim && !co) return [];
      return [`${piName(b)}: ${[sim && '주제 유사', co && `공동 논문 ${co.edge.weight}편`].filter(Boolean).join(', ')}`];
    });
    return parts.length ? parts.join(' / ') : '지도에 직접 연결 없음';
  };
  const rows: { label: string; cell: (l: Lab) => React.ReactNode }[] = [
    { label: '대학 · 학과', cell: affiliation },
    { label: '분야', cell: (l) => <div className="chip-row"><FieldChips lab={l} mode={mode} /></div> },
    { label: '연구 클러스터', cell: (l) => clusterPath(atlas, l) || NA },
    { label: '직위', cell: (l) => l.position ?? NA },
    { label: '소개', cell: introText },
    { label: '핵심 키워드', cell: (l) => <KeywordList items={l.keywords.slice(0, 5)} /> },
    {
      label: '최근 주제 (가장 최근 연도)',
      cell: (l) => {
        const last = l.keyword_timeline.at(-1);
        if (!last) return NA;
        return <><div className="muted small">{last.year}년</div><KeywordList items={last.keywords} /></>;
      },
    },
    { label: '최근 5년 논문', cell: (l) => `${l.paper_count_5y}편` },
    { label: '분야 기준 충족 논문', cell: (l) => `${l.senior_paper_count_5y}편` },
    {
      label: '대표 논문',
      cell: (l) => {
        const reps = l.representative_paper_ids.flatMap((id) => atlas.paperById.get(id) ?? []);
        if (reps.length === 0) return NA;
        return (
          <ul className="paper-list">
            {reps.map((p) => {
              const href = doiHref(p.doi) ?? p.openalex_url;
              return <li key={p.id}><a href={href} target="_blank" rel="noreferrer">{p.title}</a> ({p.year})</li>;
            })}
          </ul>
        );
      },
    },
    { label: '비교 대상 간 연결', cell: (l) => between(l, labs.filter((o) => o.id !== l.id)) },
    {
      label: '링크',
      cell: (l) => (
        <>
          <Link to={labLink(l.id)}>상세 페이지</Link>
          {l.homepage_url && <> · <a href={l.homepage_url} target="_blank" rel="noreferrer">홈페이지</a></>}
        </>
      ),
    },
  ];
  return (
    <div className="compare-wrap" tabIndex={0} role="region" aria-label="연구실 비교표, 가로로 스크롤할 수 있습니다">
      <table className="compare">
        <thead>
          <tr>
            <td />
            {labs.map((l) => (
              <th key={l.id} scope="col">
                <Link to={labLink(l.id)}>{piName(l)}</Link>
                <div className="muted small">{labTitle(l)}</div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label}>
              <th scope="row">{r.label}</th>
              {labs.map((l) => <td key={l.id}>{r.cell(l)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ShortlistPage({ mode }: { mode: Mode }) {
  const atlas = useAtlas();
  const list = useShortlist();
  const [params, setParams] = useSearchParams();
  const [copied, setCopied] = useState<string | null>(null);
  const [excluded, setExcluded] = useState<Set<string>>(new Set());

  useEffect(() => { document.title = '내 후보 · Lab Atlas'; }, []);

  // A shared link (#/shortlist?labs=a,b) shows those labs without touching the visitor's own list.
  const sharedRaw = params.get('labs');
  const sharedIds = sharedRaw === null ? null : sharedRaw.split(',').filter(Boolean);
  const ids = sharedIds ?? list.ids;
  const labs = ids.flatMap((id) => atlas.labById.get(id) ?? []);
  const unknown = ids.length - labs.length;

  const candidates = labs.filter((l) => !excluded.has(l.id));
  const compared = candidates.slice(0, MAX_COMPARE);

  const share = async () => {
    const url = `${window.location.origin}${window.location.pathname}#/shortlist?labs=${labs.map((l) => encodeURIComponent(l.id)).join(',')}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied('링크를 복사했습니다.');
    } catch {
      setCopied(url); // no clipboard permission: show the link to copy by hand
    }
  };

  return (
    <main className="page shortlist">
      <p className="crumb"><Link to="/">← 지형도</Link></p>
      <h1>내 후보</h1>
      <p className="lead">관심 있는 연구실을 담으면 비슷한 연구실을 추천하고, 담은 곳을 나란히 비교합니다.</p>

      {sharedIds && (
        <p className="notice" role="status">
          공유받은 후보 {labs.length}곳을 보고 있습니다.{' '}
          <button type="button" className="link-btn" onClick={() => { list.addAll(labs.map((l) => l.id)); setParams({}); }}>내 목록에 담기</button>
          {' · '}
          <button type="button" className="link-btn" onClick={() => setParams({})}>내 목록으로 돌아가기</button>
        </p>
      )}
      {unknown > 0 && <p className="notice" role="status">데이터에 없는 연구실 {unknown}곳은 표시하지 않았습니다.</p>}

      <SearchSection />

      <section aria-labelledby="mine-title">
        <h2 id="mine-title">담은 연구실 {labs.length > 0 && <span className="muted">{labs.length}곳</span>}</h2>
        {labs.length === 0 ? (
          <p className="empty">
            아직 담은 연구실이 없습니다. 위에서 찾거나 <Link to="/">지도</Link>에서 ☆ 담기를 눌러 보세요.
          </p>
        ) : (
          <>
            <ul className="seed-list">
              {labs.map((l) => (
                <li key={l.id}>
                  {labs.length > MAX_COMPARE && (
                    <label className="small">
                      <input type="checkbox" checked={compared.some((c) => c.id === l.id)}
                             disabled={!compared.some((c) => c.id === l.id) && compared.length >= MAX_COMPARE}
                             onChange={(e) => setExcluded((prev) => {
                               const next = new Set(prev);
                               if (e.target.checked) next.delete(l.id);
                               else next.add(l.id);
                               return next;
                             })} /> 비교
                    </label>
                  )}
                  <Link to={labLink(l.id)}>{piName(l)}</Link>
                  <span className="muted small">{l.univ_name_ko}</span>
                  {!sharedIds && <StarButton id={l.id} name={piName(l)} compact />}
                </li>
              ))}
            </ul>
            <p className="actions">
              <button type="button" className="link-btn" onClick={share}>공유 링크 복사</button>
              {!sharedIds && <> · <button type="button" className="link-btn" onClick={() => list.clear()}>모두 비우기</button></>}
            </p>
            {copied && <p className="small" role="status">{copied}</p>}
          </>
        )}
      </section>

      {labs.length >= 2 && (
        <section aria-labelledby="cmp-title">
          <h2 id="cmp-title">나란히 비교</h2>
          {labs.length > MAX_COMPARE && <p className="muted small">한 번에 {MAX_COMPARE}곳까지 비교합니다. 위 체크박스로 고르세요.</p>}
          <p className="muted small">점수나 순위 없이 수집한 사실만 나열합니다. 논문 수는 분야마다 관행이 달라 분야가 다르면 직접 비교하기 어렵습니다.</p>
          <Compare labs={compared} mode={mode} />
        </section>
      )}

      {labs.length >= 1 && <Recommendations seeds={labs} mode={mode} />}
    </main>
  );
}
