import { useQuery } from '@tanstack/react-query';

import { supabase } from '@/lib/supabase';

// Tracked-item count reads straight from Supabase (RLS already scopes
// `watches` to `auth.uid() = user_id`, per CLAUDE.md's "the RN client reads
// directly from Supabase via the anon key under RLS" convention) — no Flask
// round trip needed for a count.
export function useTrackedCount(userId: string | undefined) {
  return useQuery({
    queryKey: ['tracked-count', userId],
    queryFn: async () => {
      const { count, error } = await supabase
        .from('watches')
        .select('id', { count: 'exact', head: true })
        .eq('user_id', userId as string)
        .eq('watch_type', 'listing');
      if (error) throw error;
      return count ?? 0;
    },
    enabled: !!userId,
    staleTime: 30_000,
  });
}
