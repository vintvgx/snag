import type { Session } from '@supabase/supabase-js';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createContext, ReactNode, useContext, useEffect } from 'react';

import { signInWithApple, signInWithGoogle } from '@/lib/auth-providers';
import { supabase } from '@/lib/supabase';

const SESSION_QUERY_KEY = ['auth', 'session'] as const;

type AuthContextValue = {
  session: Session | null | undefined;
  isLoading: boolean;
  isSigningIn: boolean;
  signInWithApple: () => Promise<void>;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
  error: Error | null;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();

  // The session is a query, not local state, so the rest of the app can key
  // off `['auth', 'session']` the same way it would key off any other server
  // data (invalidate it, read it in a loader, etc).
  const sessionQuery = useQuery({
    queryKey: SESSION_QUERY_KEY,
    queryFn: async () => {
      const { data, error } = await supabase.auth.getSession();
      if (error) throw error;
      return data.session;
    },
    staleTime: Infinity,
  });

  useEffect(() => {
    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      queryClient.setQueryData(SESSION_QUERY_KEY, session);
    });
    return () => listener.subscription.unsubscribe();
  }, [queryClient]);

  const appleMutation = useMutation({ mutationFn: signInWithApple });
  const googleMutation = useMutation({ mutationFn: signInWithGoogle });
  const signOutMutation = useMutation({
    mutationFn: async () => {
      const { error } = await supabase.auth.signOut();
      if (error) throw error;
    },
    onSuccess: () => queryClient.setQueryData(SESSION_QUERY_KEY, null),
  });

  const value: AuthContextValue = {
    session: sessionQuery.data,
    isLoading: sessionQuery.isLoading,
    isSigningIn: appleMutation.isPending || googleMutation.isPending,
    signInWithApple: () => appleMutation.mutateAsync().then(() => undefined),
    signInWithGoogle: () => googleMutation.mutateAsync().then(() => undefined),
    signOut: () => signOutMutation.mutateAsync(),
    error: appleMutation.error ?? googleMutation.error ?? signOutMutation.error,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
