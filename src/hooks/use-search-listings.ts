import { useQuery } from '@tanstack/react-query';

import { searchListings } from '@/lib/api-client';

export function useSearchListings(query: string) {
  const trimmed = query.trim();

  return useQuery({
    queryKey: ['search', trimmed],
    queryFn: () => searchListings(trimmed),
    enabled: trimmed.length > 0,
    staleTime: 60_000,
    retry: 1,
  });
}
