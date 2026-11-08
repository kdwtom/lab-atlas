import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import type { Discipline, Lab } from '../types/data';
import { clusterPath, useAtlas, type Atlas } from '../data/DataContext';
import { useShortlist } from '../data/shortlist';
import StarButton from '../components/StarButton';
import { FieldChips } from '../components/LabPanel';
import { affiliation, introText, neighbourCaution, piName } from '../lib/format';
import { FIELD_LABEL, FIELD_ORDER, type Mode } from '../lib/palette';
import { bridge, loadLabVectors, meanVector, sharedTopics, topicProfiles, type LabVectors } from '../lib/recommend';

const LIMIT = 15;
const labLink = (id: string) => `/lab/${encodeURIComponent(id)}`;

/** A starting point: a field, a sub-cluster or one lab, written "field:chem", "sub:12" or "lab:<id>". */
interface Anchor { key: string; label: string; members: Lab[] }

function resolve(atlas: Atlas, key: string | null): Anchor | null {
  if (!key) return null;
  const [kind, value] = [key.slice(0, key.indexOf(':')), key.slice(key.indexOf(':') + 1)];
  if (kind === 'field' && value in FIELD_LABEL) {
    const f = value as Discipline;
    return { key, label: FIELD_LABEL[f], members: atlas.labs.filter((l) => l.disciplines.includes(f)) };
  }
  if (kind === 'sub') {
    const s = atlas.subclusterById.get(Number(value));
    if (s) return { key, label: s.label_ko, members: atlas.labs.filter((l) => l.subcluster_id === s.id) };
  }
  if (kind === 'lab') {
    const l = atlas.labById.get(value);
    if (l) return { key, label: `${piName(l)} 연구실`, members: [l] };
  }
  return null;
}

function AnchorSelect({ value, onChange, label, shortlisted }: {
  value: string; onChange: (v: string) => void; label: string; shortlisted: Lab[];
}) {
  const atlas = useAtlas();
  return (
    <label className="bridge-pick">
      <span>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <optgroup label="분야">
          {FIELD_ORDER.map((f) => <option key={f} value={`field:${f}`}>{FIELD_LABEL[f]}</option>)}
        </optgroup>
        {atlas.clusters.filter((c) => (c.subclusters?.length ?? 0) > 0).map((c) => (
          <optgroup key={c.id} label={`세부 분야 · ${c.label_ko}`}>
            {c.subclusters!.map((s) => <option key={s.id} value={`sub:${s.id}`}>{s.label_ko} ({s.size})</option>)}
          </optgroup>
        ))}
        {shortlisted.length > 0 && (
          <optgroup label="내 후보에 담은 연구실">
            {shortlisted.map((l) => <option key={l.id} value={`lab:${l.id}`}>{piName(l)} · {l.univ_name_ko}</option>)}
          </optgroup>
        )}
      </select>
    </label>
  );
}

export default function BridgePage({ mode }: { mode: Mode }) {
  const atlas = useAtlas();
  const { ids } = useShortlist();
  const [params, setParams] = useSearchParams();
  const aKey = params.get('a') ?? 'field:chem';
  const bKey = params.get('b') ?? 'field:cs';
  // off by default: a chemistry lab doing machine learning is exactly the bridge between chemistry and computing
  const [outside, setOutside] = useState(false);
  const [vectors, setVectors] = useState<LabVectors | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => { document.title = '다리 찾기 · Lab Atlas'; }, []);
  useEffect(() => {
    let alive = true;
    loadLabVectors().then((v) => { if (alive) setVectors(v); }).catch(() => { if (alive) setFailed(true); });
    return () => { alive = false; };
  }, []);

  const shortlisted = ids.flatMap((id) => atlas.labById.get(id) ?? []);
  const a = resolve(atlas, aKey);
  const b = resolve(atlas, bKey);
  const set = (k: 'a' | 'b', v: string) => {
    const next = new URLSearchParams(params);
    next.set(k, v);
    setParams(next, { replace: true });
  };
  const profiles = useMemo(() => topicProfiles(atlas.papers), [atlas.papers]);
  const anchorProfile = (an: Anchor) => {
    const m = new Map<string, number>();
    for (const l of an.members) for (const [t, w] of profiles.get(l.id) ?? []) m.set(t, (m.get(t) ?? 0) + w / an.members.length);
    return m;
  };

  const rows = useMemo(() => {
    if (!vectors || !a || !b || a.key === b.key) return [];
    const va = meanVector(vectors, a.members.map((l) => l.id));
    const vb = meanVector(vectors, b.members.map((l) => l.id));
    if (!va || !vb) return [];
    const inAnchor = new Set([...a.members, ...b.members].map((l) => l.id));
    return bridge(vectors, va, vb).flatMap((r) => {
      const lab = atlas.labById.get(r.id);
      // labs whose paper lists mix in other people's work have unreliable vectors
      if (!lab || lab.intro_unavailable === 'mixed_topics' || lab.intro_unavailable === 'wrong_field') return [];
      if (outside ? inAnchor.has(lab.id) : a.members.length === 1 && lab.id === a.members[0].id) return [];
      if (b.members.length === 1 && lab.id === b.members[0].id) return [];
      return [{ ...r, lab }];
    }).slice(0, LIMIT);
  }, [vectors, aKey, bKey, outside]); // eslint-disable-line react-hooks/exhaustive-deps -- anchors follow their keys

  const pa = a ? anchorProfile(a) : undefined;
  const pb = b ? anchorProfile(b) : undefined;
  const lean = (d: number) => (Math.abs(d) < 0.01 ? '두 쪽 가운데' : d > 0 ? `${a?.label} 쪽에 더 가까움` : `${b?.label} 쪽에 더 가까움`);

  return (
    <main className="page bridge">
      <p className="crumb"><Link to="/">← 지형도</Link></p>
      <h1>다리 찾기</h1>
      <p className="lead">
        두 출발점을 고르면, 양쪽 모두와 연구 내용이 가까운 연구실을 찾습니다. 전공을 바꾸거나 두 분야를 함께 하고 싶을 때 쓸 수 있습니다.
      </p>
      <div className="bridge-picks">
        <AnchorSelect label="출발점 A" value={aKey} onChange={(v) => set('a', v)} shortlisted={shortlisted} />
        <span className="bridge-plus" aria-hidden="true">↔</span>
        <AnchorSelect label="출발점 B" value={bKey} onChange={(v) => set('b', v)} shortlisted={shortlisted} />
      </div>
      <label className="bridge-option">
        <input type="checkbox" checked={outside} onChange={(e) => setOutside(e.target.checked)} />
        출발점에 속한 연구실은 빼고 보기
      </label>
      <p className="muted small">
        두 출발점 중 <strong>덜 가까운 쪽</strong>과의 유사도가 높은 순서입니다. 한쪽에만 아주 가까운 연구실보다 양쪽에 고르게 가까운 연구실이 위에 옵니다.
        연구실 평가가 아니며, 공유 링크로 같은 조건을 다시 열 수 있습니다.
      </p>

      {failed && <p className="notice" role="alert">유사도 데이터를 불러오지 못했습니다. 새로고침해 주세요.</p>}
      {!failed && !vectors && <p className="muted" role="status">계산하는 중…</p>}
      {a && b && a.key === b.key && <p className="empty">서로 다른 두 출발점을 골라 주세요.</p>}
      {vectors && a && b && a.key !== b.key && rows.length === 0 && <p className="empty">조건에 맞는 연구실이 없습니다.</p>}

      <ol className="lab-rows">
        {rows.map(({ lab, toA, toB }) => {
          const ta = sharedTopics(profiles.get(lab.id), pa, 2);
          const tb = sharedTopics(profiles.get(lab.id), pb, 2);
          // marker: 0 = right at A, 1 = right at B
          const pos = Math.max(0, Math.min(1, 0.5 + (toB - toA) / 0.08));
          const caution = neighbourCaution(lab);
          return (
            <li key={lab.id}>
              <StarButton id={lab.id} name={piName(lab)} compact />
              <div>
                <Link to={labLink(lab.id)} className="row-link">{piName(lab)}</Link>
                <span className="muted small"> {affiliation(lab)} · {clusterPath(atlas, lab)}</span>
                <div className="chip-row"><FieldChips lab={lab} mode={mode} /></div>
                <div className="lean" role="img" aria-label={lean(toA - toB)}>
                  <span className="lean-end">{a?.label}</span>
                  <span className="lean-track"><span className="lean-dot" style={{ left: `${pos * 100}%` }} /></span>
                  <span className="lean-end">{b?.label}</span>
                </div>
                <p className="small row-intro">{introText(lab)}</p>
                <p className="muted small">
                  {lean(toA - toB)}
                  {ta.length > 0 && ` · ${a?.label}와 공통 주제: ${ta.join(', ')}`}
                  {tb.length > 0 && ` · ${b?.label}와 공통 주제: ${tb.join(', ')}`}
                </p>
                {caution && <p className="muted small">{caution}</p>}
              </div>
            </li>
          );
        })}
      </ol>
    </main>
  );
}
