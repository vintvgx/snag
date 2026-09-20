import { useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ListingCard } from '@/components/listing-card';
import { SearchFiltersForm } from '@/components/search-filters';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { useSearchListings } from '@/hooks/use-search-listings';
import { useTheme } from '@/hooks/use-theme';
import { SearchFilters } from '@/lib/api-client';

const DEFAULT_FILTERS: SearchFilters = {
  zip: '02026',
  range: 25,
};

export default function HomeScreen() {
  const [filters, setFilters] = useState<SearchFilters>(DEFAULT_FILTERS);
  const { data, isLoading, isFetching, isError, error, refetch } = useSearchListings(filters);

  console.warn("ERROR:", error?.message)

  return (
    <ThemedView style={styles.container}>
      <SafeAreaView style={styles.safeArea} edges={['top']}>
        <FlatList
          data={data?.listings ?? []}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => <ListingCard listing={item} />}
          ItemSeparatorComponent={() => <ThemedView style={styles.separator} />}
          ListHeaderComponent={
            <ThemedView style={styles.header}>
              <ThemedText type="subtitle" themeColor="primary" style={styles.wordmark}>
                SNAG
              </ThemedText>
              <SearchFiltersForm value={filters} onSubmit={setFilters} isLoading={isFetching} />
              <ResultsSummary
                isLoading={isLoading}
                isError={isError}
                errorMessage={error?.message}
                count={data?.count}
                onRetry={refetch}
              />
            </ThemedView>
          }
          ListEmptyComponent={
            !isLoading && !isError ? (
              <ThemedText type="small" themeColor="textSecondary" style={styles.emptyText}>
                No matches for these filters yet.
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
  count,
  onRetry,
}: {
  isLoading: boolean;
  isError: boolean;
  errorMessage?: string;
  count?: number;
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

  if (count != null) {
    return (
      <ThemedText type="small" themeColor="textSecondary" style={styles.summarySpacing}>
        {count} result{count === 1 ? '' : 's'}
      </ThemedText>
    );
  }

  return null;
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
