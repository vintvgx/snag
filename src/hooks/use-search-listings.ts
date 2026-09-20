import { useQuery } from '@tanstack/react-query';

import { searchTeslaListings, SearchFilters } from '@/lib/api-client';

export function useSearchListings(filters: SearchFilters) {
  return useQuery({
    queryKey: ['search', 'tesla', filters],
    queryFn: () => searchTeslaListings(filters),
    staleTime: 60_000,
    retry: 1,
  });
}
