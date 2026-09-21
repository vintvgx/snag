import { StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { LoadingScreen } from '@/components/loading-screen';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Text } from '@/components/ui/text';
import { Spacing } from '@/constants/theme';
import { useAuth } from '@/contexts/auth-context';
import { useTrackedCount } from '@/hooks/use-profile-stats';
import { formatDate } from '@/lib/format';

export default function ProfileScreen() {
  const { session, signOut } = useAuth();

  // Same note as track.tsx: the (app) stack is already gated on a session
  // (src/app/_layout.tsx's Stack.Protected) — this is a type-safety guard,
  // not the real signed-out UX.
  if (!session) {
    return <LoadingScreen />;
  }

  return (
    <ProfileContent
      userId={session.user.id}
      email={session.user.email}
      createdAt={session.user.created_at}
      onSignOut={signOut}
    />
  );
}

function ProfileContent({
  userId,
  email,
  createdAt,
  onSignOut,
}: {
  userId: string;
  email: string | undefined;
  createdAt: string;
  onSignOut: () => Promise<void>;
}) {
  // "Date joined" comes from the auth session's own created_at, not a
  // public.users row: nothing in this project currently inserts a
  // public.users row on signup (no trigger, no Flask endpoint for it — see
  // supabase/migrations/), so it may not exist for real users yet. The
  // session's own identity timestamp is accurate regardless and sidesteps
  // that gap; worth a ticket to backfill public.users properly since
  // push_token (used for notifications) has nowhere to land without it.
  const { data: trackedCount } = useTrackedCount(userId);
  const initial = (email ?? '?').charAt(0).toUpperCase();

  return (
    <ThemedView style={styles.container}>
      <SafeAreaView style={styles.safeArea} edges={['top']}>
        <ThemedView style={styles.header}>
          <ThemedText type="subtitle" themeColor="primary">
            Profile
          </ThemedText>
        </ThemedView>

        <ThemedView style={styles.body}>
          <ThemedView style={styles.identityRow}>
            <Avatar alt={email ?? 'Profile'}>
              <AvatarFallback>
                <Text variant="large">{initial}</Text>
              </AvatarFallback>
            </Avatar>
            <ThemedView style={styles.identityText}>
              <ThemedText type="smallBold">{email ?? 'Signed in'}</ThemedText>
              <ThemedText type="small" themeColor="textSecondary">
                Joined {formatDate(createdAt)}
              </ThemedText>
            </ThemedView>
          </ThemedView>

          <Card>
            <CardContent style={styles.statsRow}>
              <ThemedView style={styles.stat}>
                <ThemedText type="subtitle">{trackedCount ?? '—'}</ThemedText>
                <ThemedText type="small" themeColor="textSecondary">
                  Tracked
                </ThemedText>
              </ThemedView>
            </CardContent>
          </Card>

          <ThemedView style={styles.settingsSection}>
            <ThemedText type="smallBold" themeColor="textSecondary">
              Settings
            </ThemedText>
            <Card>
              <CardContent style={styles.settingsList}>
                <SettingsRow label="Notification preferences" comingSoon />
                <Separator />
                <SettingsRow label="Payment & purchase history" comingSoon />
              </CardContent>
            </Card>

            <Button variant="outline" onPress={() => onSignOut().catch(() => {})}>
              <Text>Sign Out</Text>
            </Button>
          </ThemedView>
        </ThemedView>
      </SafeAreaView>
    </ThemedView>
  );
}

function SettingsRow({ label, comingSoon }: { label: string; comingSoon?: boolean }) {
  return (
    <ThemedView style={styles.settingsRow}>
      <Text variant={comingSoon ? 'muted' : 'default'}>{label}</Text>
      {comingSoon && (
        <Text variant="muted" className="text-xs">
          Coming soon
        </Text>
      )}
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  safeArea: {
    flex: 1,
  },
  header: {
    paddingHorizontal: Spacing.four,
    paddingBottom: Spacing.three,
  },
  body: {
    paddingHorizontal: Spacing.four,
    gap: Spacing.four,
  },
  identityRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.three,
  },
  identityText: {
    gap: 2,
  },
  statsRow: {
    flexDirection: 'row',
  },
  stat: {
    alignItems: 'center',
    gap: 2,
  },
  settingsSection: {
    gap: Spacing.two,
  },
  settingsList: {
    gap: Spacing.two,
  },
  settingsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: Spacing.one,
  },
});
