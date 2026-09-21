import { FlatList, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { LoadingScreen } from '@/components/loading-screen';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Text } from '@/components/ui/text';
import { Spacing } from '@/constants/theme';
import { useAuth } from '@/contexts/auth-context';
import { useWatches } from '@/hooks/use-watches';
import { Watch } from '@/lib/api-client';
import { formatRelativeTime } from '@/lib/format';

const SOURCE_LABELS: Record<string, string> = {
  tesla: 'Tesla',
  ebay: 'eBay',
  amazon: 'Amazon',
  google: 'Google',
  web: 'Web',
};

const currencyFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
});

export default function TrackScreen() {
  const { session } = useAuth();

  // The (app) stack is already gated on a session (see src/app/_layout.tsx's
  // Stack.Protected) — this is just a type-safety guard for `session.user.id`
  // below, not the real signed-out UX. The router redirects to (auth) before
  // this screen would ever mount without one.
  if (!session) {
    return <LoadingScreen />;
  }

  return <TrackList userId={session.user.id} />;
}

function TrackList({ userId }: { userId: string }) {
  const { data, isLoading, isFetching, isError, error, refetch } = useWatches(userId);
  const listingWatches = (data ?? []).filter((watch) => watch.watch_type === 'listing');

  return (
    <ThemedView style={styles.container}>
      <SafeAreaView style={styles.safeArea} edges={['top']}>
        <FlatList
          data={listingWatches}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => <WatchCard watch={item} />}
          ItemSeparatorComponent={() => <ThemedView style={styles.separator} />}
          onRefresh={refetch}
          refreshing={isFetching && !isLoading}
          ListHeaderComponent={
            <ThemedView style={styles.header}>
              <ThemedText type="subtitle" themeColor="primary">
                Track
              </ThemedText>
            </ThemedView>
          }
          ListEmptyComponent={
            !isLoading ? (
              <ThemedText type="small" themeColor="textSecondary" style={styles.emptyText}>
                {isError
                  ? (error?.message ?? 'Something went wrong loading your tracked items.')
                  : "You're not tracking anything yet — search for an item on Home and tap Track."}
              </ThemedText>
            ) : null
          }
          contentContainerStyle={styles.listContent}
        />
      </SafeAreaView>
    </ThemedView>
  );
}

function WatchCard({ watch }: { watch: Watch }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{watch.name}</CardTitle>
      </CardHeader>
      <CardContent style={styles.cardRow}>
        <Badge variant="secondary">
          <Text>{SOURCE_LABELS[watch.source] ?? watch.source}</Text>
        </Badge>
        {watch.target_price != null && (
          <Text variant="muted">
            Notify at or below {currencyFormatter.format(watch.target_price)}
          </Text>
        )}
      </CardContent>
      <CardFooter style={[styles.cardRow, styles.cardFooter]}>
        <Badge variant={watch.status === 'active' ? 'default' : 'outline'}>
          <Text>{watch.status}</Text>
        </Badge>
        <Text variant="muted">Tracking since {formatRelativeTime(watch.created_at)}</Text>
      </CardFooter>
    </Card>
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
  listContent: {
    paddingHorizontal: Spacing.four,
    paddingBottom: Spacing.six,
    gap: Spacing.two,
  },
  separator: {
    height: Spacing.two,
  },
  cardRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
  },
  cardFooter: {
    justifyContent: 'space-between',
  },
  emptyText: {
    textAlign: 'center',
    marginTop: Spacing.four,
    paddingHorizontal: Spacing.four,
  },
});
