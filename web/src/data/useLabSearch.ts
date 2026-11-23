import { useMemo } from 'react';
import { useAtlas } from './DataContext';
import { filterKey, searchLabs, type SearchFilters, type SearchOptions } from '../lib/search/index';
export function useLabSearch(query: string, filters: SearchFilters, options: SearchOptions = {}) {
  const atlas = useAtlas();
  const key = filterKey(filters);
  return useMemo(() => searchLabs(atlas.searchIndex(), query, filters, options),
    [atlas, query, key, options.keyboardCorrection, options.includeUnfilteredCount]);
}
