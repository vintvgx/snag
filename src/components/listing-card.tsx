import { Linking, Pressable, StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Listing } from '@/lib/api-client';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

const currencyFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
});

function Chip({ label }: { label: string }) {
  const theme = useTheme();
  return (
    <ThemedView type="backgroundElement" style={[styles.chip, { borderColor: theme.backgroundSelected }]}>
      <ThemedText type="small">{label}</ThemedText>
    </ThemedView>
  );
}

export function ListingCard({ listing }: { listing: Listing }) {
  const theme = useTheme();
  const { attrs, location, seller } = listing;

  const chips = [
    attrs.year && String(attrs.year),
    attrs.trim,
    attrs.drivetrain,
    attrs.odometer != null && `${Number(attrs.odometer).toLocaleString()} mi`,
  ].filter(Boolean) as string[];

  const locationLabel = [location.city, location.state].filter(Boolean).join(', ');

  return (
    <Pressable
      onPress={() => Linking.openURL(listing.url)}
      style={({ pressed }) => [styles.pressable, { opacity: pressed ? 0.8 : 1 }]}>
      <ThemedView type="backgroundElement" style={styles.card}>
        <View style={styles.headerRow}>
          <ThemedText type="smallBold" style={styles.title} numberOfLines={1}>
            {listing.title}
          </ThemedText>
          <ThemedText type="smallBold" style={{ color: theme.primary }}>
            {currencyFormatter.format(listing.price)}
          </ThemedText>
        </View>

        {chips.length > 0 && (
          <View style={styles.chipRow}>
            {chips.map((chip) => (
              <Chip key={chip} label={chip} />
            ))}
          </View>
        )}

        <View style={styles.footerRow}>
          <ThemedText type="small" themeColor="textSecondary">
            {locationLabel || 'Location unavailable'}
          </ThemedText>
          <TrustBadge seller={seller} />
        </View>
      </ThemedView>
    </Pressable>
  );
}

function TrustBadge({ seller }: { seller: Listing['seller'] }) {
  const theme = useTheme();

  if (seller.is_official_source) {
    return (
      <ThemedText type="small" style={{ color: theme.primary, fontWeight: '700' }}>
        Sold directly by {seller.display_name ?? 'source'}
      </ThemedText>
    );
  }

  if (seller.rating != null) {
    return (
      <ThemedText type="small" themeColor="textSecondary">
        ★ {seller.rating} ({seller.review_count ?? 0})
      </ThemedText>
    );
  }

  // Never invent a trust score when a source has no seller signal.
  return (
    <ThemedText type="small" themeColor="textSecondary">
      Limited trust data
    </ThemedText>
  );
}

const styles = StyleSheet.create({
  pressable: {
    width: '100%',
  },
  card: {
    borderRadius: Spacing.three,
    padding: Spacing.three,
    gap: Spacing.two,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: Spacing.two,
  },
  title: {
    flex: 1,
  },
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.one,
  },
  chip: {
    borderRadius: Spacing.five,
    borderWidth: 1,
    paddingHorizontal: Spacing.two,
    paddingVertical: 2,
  },
  footerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
});
