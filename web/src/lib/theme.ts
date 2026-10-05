import { useEffect, useState } from 'react';
import type { Mode } from './palette';

export type ThemeChoice = 'system' | 'light' | 'dark';
const KEY = 'lab-atlas-theme';

function systemMode(): Mode {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function readChoice(): ThemeChoice {
  try {
    const v = localStorage.getItem(KEY);
    if (v === 'light' || v === 'dark' || v === 'system') return v;
  } catch {
    /* storage unavailable: fall back to system */
  }
  return 'system';
}

/** Theme choice (persisted per browser) and the resolved light/dark mode. */
export function useTheme(): { choice: ThemeChoice; mode: Mode; setChoice: (c: ThemeChoice) => void } {
  const [choice, setChoiceState] = useState<ThemeChoice>(readChoice);
  const [sys, setSys] = useState<Mode>(systemMode);

  useEffect(() => {
    const mq = window.matchMedia?.('(prefers-color-scheme: dark)');
    if (!mq) return;
    const onChange = () => setSys(systemMode());
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  const mode: Mode = choice === 'system' ? sys : choice;
  useEffect(() => {
    const root = document.documentElement;
    if (choice === 'system') root.removeAttribute('data-theme');
    else root.setAttribute('data-theme', choice);
  }, [choice]);

  const setChoice = (c: ThemeChoice) => {
    setChoiceState(c);
    try {
      localStorage.setItem(KEY, c);
    } catch {
      /* ignore */
    }
  };
  return { choice, mode, setChoice };
}
