import { Link } from 'react-router-dom';
import type { Lab } from '../types/data';
import { useAtlas } from '../data/DataContext';
import { piName } from '../lib/format';

const labLink = (id: string) => `/lab/${encodeURIComponent(id)}`;

/** Where the lab's research is heading: first two years of the window against the last two (pipeline/trend.py). */
export default function TrendSection({ lab, compact = false }: { lab: Lab; compact?: boolean }) {
  const atlas = useAtlas();
  const t = lab.trend;
  if (!t) return null;
  const [e0, e1] = t.early_years;
  const [r0, r1] = t.recent_years;
  const periods = `${e0}–${e1}년(${t.early_papers}편)과 ${r0}–${r1}년(${t.recent_papers}편)`;
  if (t.status === 'insufficient') {
    return compact ? null : (
      <p className="muted">기간별 논문이 4편 미만이라 판단하지 않았습니다({periods} 논문 비교).</p>
    );
  }
  const sub = (id: number | null | undefined) => (id == null ? undefined : atlas.subclusterById.get(id)?.label_ko);
  const toward = sub(t.toward_subcluster_id);
  const away = sub(t.away_subcluster_id);
  const towardLabs = (t.toward_lab_ids ?? []).flatMap((id) => atlas.labById.get(id) ?? []);
  const topics = (label: string, list: string[] | undefined) => (list?.length ? (
    <div className="trend-topics">
      <span className="trend-label">{label}</span>
      <ul className="tags">{list.map((k) => <li key={k}>{k}</li>)}</ul>
    </div>
  ) : null);

  return (
    <div className="trend">
      {t.status === 'shifted' ? (
        <p>
          <strong>최근 연구 주제가 달라진 신호가 있습니다.</strong>
          {toward && <> 최근 논문은 <strong>{toward}</strong> 쪽으로 가까워졌습니다{away ? <>(멀어진 분야: {away})</> : null}.</>}
          {!compact && ' 이렇게 표시된 연구실 중 약 5곳에 1곳은 우연일 수 있습니다. 지도에서 이 연구실을 선택하면 2022–23년 논문 위치에서 2025–26년 논문 위치로 향하는 화살표와, 최근 가까워진 연구실이 표시됩니다.'}
        </p>
      ) : (
        <p>
          <strong>뚜렷한 주제 변화는 확인되지 않았습니다.</strong>{' '}
          {compact ? '두 기간 논문의 차이가 표본에 따른 흔들림과 구분되지 않습니다.' : `${periods} 논문의 주제 차이가 논문 표본에 따른 흔들림과 구분되지 않습니다. 변화가 전혀 없다는 뜻은 아닙니다.`}
        </p>
      )}
      {/* topic changes of labs without a clear shift would read as change when they are mostly noise */}
      {t.status === 'shifted' && topics('최근 늘어난 주제', t.emerging_topics)}
      {t.status === 'shifted' && !compact && topics('줄어든 주제', t.fading_topics)}
      {!compact && towardLabs.length > 0 && (
        <p className="small">
          최근 논문이 가까워진 연구실:{' '}
          {towardLabs.map((o, i) => (
            <span key={o.id}>{i > 0 && ', '}<Link to={labLink(o.id)}>{piName(o)}</Link></span>
          ))}
        </p>
      )}
      {!compact && (
        <p className="muted small">
          {periods} 논문을 비교했습니다. 주제 변화는 연구실 평가가 아니며, 공동연구나 학생 졸업 같은 사정으로도 생길 수 있습니다.
          판단 방법은 <Link to="/about#trend">방법론</Link>에 있습니다.
        </p>
      )}
    </div>
  );
}
