import { useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ListingCard } from '@/components/listing-card';
import { SearchBar } from '@/components/search-bar';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { useSearchListings } from '@/hooks/use-search-listings';
import { useTheme } from '@/hooks/use-theme';
import { SearchResponse } from '@/lib/api-client';
import { formatRelativeTime } from '@/lib/format';

const SOURCE_LABELS: Record<string, string> = {
  tesla: 'Tesla',
  ebay: 'eBay',
  amazon: 'Amazon',
  google: 'Google',
  web: 'Web',
};

export default function HomeScreen() {
  const [submittedQuery, setSubmittedQuery] = useState('');
  const { data, isLoading, isFetching, isError, error, refetch } = useSearchListings(submittedQuery);

  return (
    <ThemedView style={styles.container}>
      <SafeAreaView style={styles.safeArea} edges={['top']}>
        <FlatList
          data={data?.listings ?? []}
          keyExtractor={(item) => `${item.source}:${item.id}`}
          renderItem={({ item }) => <ListingCard listing={item} />}
          ItemSeparatorComponent={() => <ThemedView style={styles.separator} />}
          onRefresh={submittedQuery ? refetch : undefined}
          refreshing={isFetching && !isLoading}
          ListHeaderComponent={
            <ThemedView style={styles.header}>
              <ThemedText type="subtitle" themeColor="primary" style={styles.wordmark}>
                SNAG
              </ThemedText>
              <SearchBar value={submittedQuery} onSubmit={setSubmittedQuery} isLoading={isLoading} />
              {submittedQuery.length > 0 && (
                <ResultsSummary
                  isLoading={isLoading}
                  isError={isError}
                  errorMessage={error?.message}
                  data={data}
                  onRetry={refetch}
                />
              )}
            </ThemedView>
          }
          ListEmptyComponent={
            !isLoading && !isError ? (
              <ThemedText type="small" themeColor="textSecondary" style={styles.emptyText}>
                {submittedQuery
                  ? `No matches yet for “${submittedQuery}.”`
                  : 'Search for an item to see live listings — try one of the suggestions above.'}
              </ThemedText>
            ) : null
          }
          contentContainerStyle={styles.listContent}
        />
      </SafeAreaView>
    </ThemedView>
  );
}

function ResultsSummary({
  isLoading,
  isError,
  errorMessage,
  data,
  onRetry,
}: {
  isLoading: boolean;
  isError: boolean;
  errorMessage?: string;
  data?: SearchResponse;
  onRetry: () => void;
}) {
  const theme = useTheme();

  if (isLoading) {
    return <ActivityIndicator style={styles.summarySpacing} color={theme.primary} />;
  }

  if (isError) {
    return (
      <ThemedView style={styles.summarySpacing}>
        <ThemedText type="small" themeColor="primary">
          {errorMessage ?? 'Something went wrong reaching the search API.'}
        </ThemedText>
        <Pressable onPress={onRetry}>
          <ThemedText type="linkPrimary">Retry</ThemedText>
        </Pressable>
      </ThemedView>
    );
  }

  if (!data) {
    return null;
  }

  return (
    <View style={styles.summarySpacing}>
      <View style={styles.summaryHeaderRow}>
        <ThemedText type="small" themeColor="textSecondary">
          {data.count} result{data.count === 1 ? '' : 's'} · {data.cached ? 'cached' : 'live'}, checked{' '}
          {formatRelativeTime(data.last_searched_at)}
        </ThemedText>
        {data.in_progress && <ActivityIndicator size="small" />}
      </View>
      <View style={styles.statusRow}>
        {Object.entries(data.sources_status).map(([source, status]) => (
          <ThemedText key={source} type="small" themeColor="textSecondary" style={styles.statusChip}>
            {SOURCE_LABELS[source] ?? source}: {describeStatus(status)}
          </ThemedText>
        ))}
      </View>
    </View>
  );
}

function describeStatus(status: string): string {
  if (status === 'ok') return 'ok';
  if (status === 'pending') return 'still searching…';
  if (status === 'timeout') return 'timed out';
  if (status.startsWith('unavailable')) return 'not set up yet';
  if (status.startsWith('schema_drift')) return 'needs attention';
  return status;
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
    gap: Spacing.two,
  },
  wordmark: {
    letterSpacing: 2,
  },
  summarySpacing: {
    marginTop: Spacing.one,
    gap: Spacing.one,
  },
  summaryHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
  },
  statusRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.two,
  },
  statusChip: {
    opacity: 0.8,
  },
  listContent: {
    paddingHorizontal: Spacing.four,
    paddingBottom: Spacing.six,
  },
  separator: {
    height: Spacing.two,
  },
  emptyText: {
    textAlign: 'center',
    marginTop: Spacing.four,
  },
});
