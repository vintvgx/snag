import { useQuery } from '@tanstack/react-query';

import { listWatches } from '@/lib/api-client';

export function useWatches(userId: string | undefined) {
  return useQuery({
    queryKey: ['watches', userId],
    queryFn: () => listWatches(userId as string),
    enabled: !!userId,
    staleTime: 30_000,
  });
}
