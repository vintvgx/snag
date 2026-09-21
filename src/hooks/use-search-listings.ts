import { useQuery } from '@tanstack/react-query';

import { searchListings, SearchResponse } from '@/lib/api-client';

// Fast sources (eBay/Amazon) usually resolve inside the backend's own
// response window; slower ones (Google/SerpApi's live scrape) can still be
// running when the first response comes back with `in_progress: true`.
// Poll at this interval until nothing's pending anymore, so results fill in
// instead of forcing the client to wait for the slowest source up front.
const POLL_INTERVAL_MS = 2_500;

export function useSearchListings(query: string) {
  const trimmed = query.trim();

  return useQuery({
    queryKey: ['search', trimmed],
    queryFn: () => searchListings(trimmed),
    enabled: trimmed.length > 0,
    staleTime: 60_000,
    retry: 1,
    refetchInterval: (query) => {
      const data = query.state.data as SearchResponse | undefined;
      return data?.in_progress ? POLL_INTERVAL_MS : false;
    },
  });
}
