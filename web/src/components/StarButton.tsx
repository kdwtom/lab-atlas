import { useShortlist } from '../data/shortlist';

/** Adds a lab to, or removes it from, the visitor's shortlist. */
export default function StarButton({ id, name, compact }: { id: string; name: string; compact?: boolean }) {
  const { has, toggle } = useShortlist();
  const on = has(id);
  return (
    <button type="button" className={compact ? 'star compact' : 'star'} aria-pressed={on}
            aria-label={`${name} ${on ? '후보에서 빼기' : '후보에 담기'}`}
            title={on ? '후보에서 빼기' : '후보에 담기'}
            onClick={(e) => { e.stopPropagation(); toggle(id); }}>
      <span aria-hidden="true">{on ? '★' : '☆'}</span>{!compact && (on ? ' 담음' : ' 담기')}
    </button>
  );
}
