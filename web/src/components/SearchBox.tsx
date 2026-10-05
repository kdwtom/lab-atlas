import { useId, useMemo, useState, type KeyboardEvent } from 'react';
import type { Lab } from '../types/data';
import { matchesQuery } from '../data/explore';
import { affiliation, piName } from '../lib/format';

interface Props {
  labs: Lab[];
  query: string;
  onQuery: (q: string) => void;
  onPick: (lab: Lab) => void;
}

/** Accessible combobox: type to filter, ↑/↓ to move, Enter to pick, Esc to close. */
export default function SearchBox({ labs, query, onQuery, onPick }: Props) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const results = useMemo(() => (query.trim() ? labs.filter((l) => matchesQuery(l, query)).slice(0, 8) : []), [labs, query]);
  const show = open && results.length > 0;

  const pick = (lab: Lab) => {
    onPick(lab);
    setOpen(false);
  };
  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setOpen(true);
      setActive((a) => Math.min(a + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === 'Enter' && show) {
      e.preventDefault();
      pick(results[active]);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  return (
    <div className="search">
      <label htmlFor={`${id}-input`} className="sr-only">연구실, PI 이름, 키워드 검색</label>
      <input
        id={`${id}-input`}
        type="search"
        role="combobox"
        aria-expanded={show}
        aria-controls={`${id}-list`}
        aria-activedescendant={show ? `${id}-opt-${active}` : undefined}
        aria-autocomplete="list"
        placeholder="연구실 · PI 이름(한/영) · 키워드 검색"
        value={query}
        onChange={(e) => {
          onQuery(e.target.value);
          setOpen(true);
          setActive(0);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onKeyDown={onKey}
      />
      {show && (
        <ul id={`${id}-list`} role="listbox" className="search-list">
          {results.map((lab, i) => (
            <li
              key={lab.id}
              id={`${id}-opt-${i}`}
              role="option"
              aria-selected={i === active}
              className={i === active ? 'active' : ''}
              onMouseDown={(e) => {
                e.preventDefault();
                pick(lab);
              }}
              onMouseEnter={() => setActive(i)}
            >
              <span className="opt-name">{piName(lab)}{lab.pi_name_en && lab.pi_name_ko ? ` · ${lab.pi_name_en}` : ''}</span>
              <span className="opt-sub">{affiliation(lab)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
