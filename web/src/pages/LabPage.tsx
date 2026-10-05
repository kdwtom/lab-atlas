import { useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import type { Paper, PaperSummary, SourceKind } from '../types/data';
import { useAtlas } from '../data/DataContext';
import { NA, affiliation, doiHref, fmtDate, labTitle, piName } from '../lib/format';
import type { Mode } from '../lib/palette';
import { ClusterChip } from '../components/LabPanel';

const SUMMARY_FIELDS: [keyof PaperSummary, string][] = [
  ['background', '연구 배경'],
  ['methods', '방법'],
  ['findings', '핵심 발견'],
  ['significance', '의의'],
];

const SOURCE_LABEL: Record<SourceKind, string> = {
  faculty_page: '학과 교수진 페이지',
  faculty_detail: '교수 상세 페이지',
  openalex_author: 'OpenAlex 저자 정보',
  openalex_works: 'OpenAlex 논문 목록',
  semantic_scholar: 'Semantic Scholar (TLDR)',
  homepage: '연구실 홈페이지',
};

const ROLE_LABEL = { first: '제1저자', middle: '공저자', last: '마지막 저자' } as const;

function PaperCard({ paper, labId }: { paper: Paper; labId: string }) {
  const role = paper.pi_roles[labId];
  const doi = doiHref(paper.doi);
  const s = paper.summary_ko;
  return (
    <article className="card paper">
      <p className="eyebrow">
        {paper.year} · {paper.venue ?? NA} · 인용 {paper.cited_by_count}회
        {role && ` · ${ROLE_LABEL[role.position]}${role.is_corresponding ? '·교신저자' : ''}`}
      </p>
      <h3 className="paper-title">{paper.title}</h3>
      <p className={s ? 'one-line' : 'one-line muted'}>{s?.one_line ?? `한 줄 요약: ${NA}`}</p>
      {s ? (
        <dl className="summary">
          {SUMMARY_FIELDS.map(([k, label]) => (
            <div key={k}>
              <dt>{label}</dt>
              <dd className={s[k] === '초록에서 확인 불가' ? 'muted' : ''}>{s[k]}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="muted small">이 논문의 한국어 요약은 아직 작성되지 않았습니다.</p>
      )}
      <p className="links">
        {doi ? <a href={doi} target="_blank" rel="noreferrer">DOI 원문</a> : <span className="muted">DOI {NA}</span>}
        <a href={paper.openalex_url} target="_blank" rel="noreferrer">OpenAlex</a>
      </p>
    </article>
  );
}

export default function LabPage({ mode }: { mode: Mode }) {
  const { id = '' } = useParams();
  const atlas = useAtlas();
  const lab = atlas.labById.get(id);

  useEffect(() => {
    document.title = lab ? `${piName(lab)} · Lab Atlas` : 'Lab Atlas';
    window.scrollTo(0, 0);
  }, [lab]);

  if (!lab) {
    return (
      <main className="page">
        <h1>연구실을 찾을 수 없습니다</h1>
        <p><Link to="/">지형도로 돌아가기</Link></p>
      </main>
    );
  }

  const reps = lab.representative_paper_ids.map((p) => atlas.paperById.get(p)).filter((p): p is Paper => !!p);
  const similar = atlas.neighbors(lab.id, 'similarity').slice(0, 5);
  const coauthors = atlas.neighbors(lab.id, 'coauthor');
  const retrieved = lab.sources.map((s) => s.retrieved_at).sort().at(-1);

  return (
    <main className="page lab-page">
      <p className="crumb"><Link to="/">← 지형도</Link></p>
      <header className="lab-head">
        <p className="eyebrow">{affiliation(lab)} · {lab.position ?? '직위 정보 없음'}</p>
        <h1>
          {piName(lab)}
          {lab.pi_name_en && lab.pi_name_ko && <span className="en"> {lab.pi_name_en}</span>}
        </h1>
        <p className="lab-name">{labTitle(lab)}</p>
        <div className="head-meta">
          <ClusterChip id={lab.cluster_id} mode={mode} />
          <span>최근 5년 논문 <strong>{lab.paper_count_5y}</strong>편</span>
          <span>마지막·교신저자 <strong>{lab.senior_paper_count_5y}</strong>편</span>
          <span title="OpenAlex 저자 매칭 근거의 강도">
            매칭 신뢰도 {lab.match_confidence === 'high' ? '높음(대표 논문 확인)' : '보통(이름·소속·주제)'}
          </span>
        </div>
      </header>

      <section>
        <h2>연구실 소개</h2>
        <p className={lab.intro_ko ? 'lead' : 'muted'}>{lab.intro_ko ?? NA}</p>
        {lab.keywords.length > 0 && <ul className="tags">{lab.keywords.map((k) => <li key={k}>{k}</li>)}</ul>}
      </section>

      <section>
        <h2>대표 논문</h2>
        <p className="muted small">
          마지막·교신저자이고 초록이 있는 논문 중 연간 인용 수 순으로 선정(최근 2년 이내 논문 최소 1편 포함).
          요약은 초록과 TLDR만을 근거로 작성했습니다.
        </p>
        {reps.length ? (
          <div className="cards">{reps.map((p) => <PaperCard key={p.id} paper={p} labId={lab.id} />)}</div>
        ) : <p className="muted">{NA}</p>}
      </section>

      <section>
        <h2>연도별 주요 키워드</h2>
        {lab.keyword_timeline.length ? (
          <ol className="timeline">
            {lab.keyword_timeline.map((t) => (
              <li key={t.year}>
                <span className="year">{t.year}</span>
                <ul className="tags">{t.keywords.map((k) => <li key={k}>{k}</li>)}</ul>
              </li>
            ))}
          </ol>
        ) : <p className="muted">{NA}</p>}
      </section>

      <div className="two-col">
        <section>
          <h2>비슷한 연구실 Top 5</h2>
          {similar.length ? (
            <ol className="neighbors">
              {similar.map(({ lab: o, edge }) => (
                <li key={o.id}>
                  <Link to={`/lab/${encodeURIComponent(o.id)}`}>{piName(o)}</Link>
                  <span className="muted small"> {o.univ_name_ko} · 유사도 {edge.weight.toFixed(3)}</span>
                  <div className="small">공통 키워드: {edge.reasons.length ? edge.reasons.join(' · ') : NA}</div>
                </li>
              ))}
            </ol>
          ) : <p className="muted">임계값을 넘는 유사 연구실이 없습니다.</p>}
        </section>
        <section>
          <h2>공동연구 연구실</h2>
          {coauthors.length ? (
            <ul className="neighbors">
              {coauthors.map(({ lab: o, edge }) => (
                <li key={o.id}>
                  <Link to={`/lab/${encodeURIComponent(o.id)}`}>{piName(o)}</Link>
                  <span className="muted small"> {o.univ_name_ko} · 공동 논문 {edge.weight}편</span>
                  <ul className="small paper-list">
                    {edge.paper_ids.slice(0, 3).map((pid) => {
                      const p = atlas.paperById.get(pid);
                      return p ? <li key={pid}><a href={doiHref(p.doi) ?? p.openalex_url} target="_blank" rel="noreferrer">{p.title}</a> ({p.year})</li> : null;
                    })}
                  </ul>
                </li>
              ))}
            </ul>
          ) : <p className="muted">데이터셋 안의 공동 논문이 없습니다.</p>}
        </section>
      </div>

      <section>
        <h2>링크</h2>
        <ul className="link-list">
          <li>{lab.homepage_url ? <a href={lab.homepage_url} target="_blank" rel="noreferrer">연구실 홈페이지</a> : <span className="muted">연구실 홈페이지: {NA}</span>}</li>
          <li><a href={lab.faculty_page_url} target="_blank" rel="noreferrer">학과 교수진 페이지</a></li>
          <li><a href={`https://openalex.org/${lab.openalex_id}`} target="_blank" rel="noreferrer">OpenAlex 저자 정보 ({lab.openalex_id})</a></li>
          <li>{lab.orcid ? <a href={`https://orcid.org/${lab.orcid}`} target="_blank" rel="noreferrer">ORCID {lab.orcid}</a> : <span className="muted">ORCID: {NA}</span>}</li>
        </ul>
      </section>

      <section className="sources">
        <h2>데이터 출처</h2>
        <ul>
          {lab.sources.map((s) => (
            <li key={s.url + s.kind}>
              <a href={s.url} target="_blank" rel="noreferrer">{SOURCE_LABEL[s.kind]}</a>
              <span className="muted small"> · 수집 {fmtDate(s.retrieved_at)}</span>
            </li>
          ))}
        </ul>
        <p className="muted small">
          {retrieved && `마지막 수집일 ${fmtDate(retrieved)}. `}정보가 틀렸다면 <Link to="/about#correction">수정 요청</Link>을 남겨 주세요.
        </p>
      </section>
    </main>
  );
}
