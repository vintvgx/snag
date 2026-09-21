import { Popover } from '@expo/ui/swift-ui';
import { useMutation } from '@tanstack/react-query';
import { Image } from 'expo-image';
import { useState } from 'react';
import { Linking, Platform, Pressable, StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Button } from '@/components/ui/button';
import { Text } from '@/components/ui/text';
import { Spacing } from '@/constants/theme';
import { useAuth } from '@/contexts/auth-context';
import { useTheme } from '@/hooks/use-theme';
import { createListingWatch, Listing } from '@/lib/api-client';

const currencyFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
});

const SOURCE_LABELS: Record<string, string> = {
  tesla: 'Tesla',
  ebay: 'eBay',
  amazon: 'Amazon',
  google: 'via Google',
  web: 'Web',
};

function Chip({ label }: { label: string }) {
  const theme = useTheme();
  return (
    <ThemedView type="backgroundElement" style={[styles.chip, { borderColor: theme.backgroundSelected }]}>
      <ThemedText type="small">{label}</ThemedText>
    </ThemedView>
  );
}

function buildChips(attrs: Listing['attrs']): string[] {
  const chips: (string | null | undefined)[] = [
    attrs.year != null ? String(attrs.year) : null,
    attrs.trim != null ? String(attrs.trim) : null,
    attrs.drivetrain != null ? String(attrs.drivetrain) : null,
    attrs.odometer != null ? `${Number(attrs.odometer).toLocaleString()} mi` : null,
    attrs.brand != null ? String(attrs.brand) : null,
    attrs.condition != null ? String(attrs.condition) : null,
    attrs.availability != null
      ? String(attrs.availability).replace(/^https?:\/\/schema\.org\//, '')
      : null,
  ];
  // De-dupe (brand/condition can coincide across sources) while preserving order.
  return Array.from(new Set(chips.filter((chip): chip is string => Boolean(chip))));
}

// Not every source's attrs carries an image (eBay and web/GenericURL do via
// `image_url`; Amazon and Google/SerpApi currently don't) — omit the image
// slot rather than fabricating a placeholder when it's missing.
function getImageUrl(attrs: Listing['attrs']): string | null {
  return typeof attrs.image_url === 'string' ? attrs.image_url : null;
}

export function ListingCard({ listing }: { listing: Listing }) {
  const [isPresented, setIsPresented] = useState(false);

  // The item-preview Popover (@expo/ui/swift-ui) only exists on iOS — no
  // Android/web equivalent ships in that package. Per the decision already
  // made, everywhere else keeps today's plain behavior: tap opens the URL
  // directly.
  if (Platform.OS !== 'ios') {
    return (
      <Pressable
        onPress={() => Linking.openURL(listing.url)}
        style={({ pressed }) => [styles.pressable, { opacity: pressed ? 0.8 : 1 }]}>
        <ListingCardBody listing={listing} />
      </Pressable>
    );
  }

  return (
    <Popover isPresented={isPresented} onIsPresentedChange={setIsPresented} arrowEdge="top">
      <Popover.Trigger>
        <Pressable
          onPress={() => setIsPresented(true)}
          style={({ pressed }) => [styles.pressable, { opacity: pressed ? 0.8 : 1 }]}>
          <ListingCardBody listing={listing} />
        </Pressable>
      </Popover.Trigger>
      <Popover.Content>
        <ItemPreview listing={listing} onDismiss={() => setIsPresented(false)} />
      </Popover.Content>
    </Popover>
  );
}

function ListingCardBody({ listing }: { listing: Listing }) {
  const theme = useTheme();
  const { attrs, location, seller, source } = listing;

  const chips = buildChips(attrs);
  const imageUrl = getImageUrl(attrs);
  const locationLabel = [location.city, location.state].filter(Boolean).join(', ');
  const subtitle = locationLabel || seller.display_name || 'Online listing';

  return (
    <ThemedView type="backgroundElement" style={styles.card}>
      <View style={styles.cardRow}>
        {imageUrl && (
          <Image source={{ uri: imageUrl }} style={styles.thumbnail} contentFit="cover" />
        )}

        <View style={styles.cardContent}>
          <View style={styles.headerRow}>
            <ThemedText type="smallBold" style={styles.title} numberOfLines={2}>
              {listing.title}
            </ThemedText>
            <ThemedText type="smallBold" style={{ color: theme.primary }}>
              {currencyFormatter.format(listing.price)}
            </ThemedText>
          </View>

          <SourceBadge source={source} />

          {chips.length > 0 && (
            <View style={styles.chipRow}>
              {chips.map((chip) => (
                <Chip key={chip} label={chip} />
              ))}
            </View>
          )}

          <View style={styles.footerRow}>
            <ThemedText
              type="small"
              themeColor="textSecondary"
              numberOfLines={1}
              style={styles.subtitle}>
              {subtitle}
            </ThemedText>
            <TrustBadge seller={seller} />
          </View>

          {source === 'google' && (
            <ThemedText type="small" themeColor="textSecondary" style={styles.discoveryNote}>
              Opens Google&apos;s price comparison page — direct retailer links are next.
            </ThemedText>
          )}
        </View>
      </View>
    </ThemedView>
  );
}

function ItemPreview({ listing, onDismiss }: { listing: Listing; onDismiss: () => void }) {
  const { session } = useAuth();
  const imageUrl = getImageUrl(listing.attrs);
  const chips = buildChips(listing.attrs);

  const trackMutation = useMutation({
    mutationFn: () => {
      if (!session) {
        throw new Error('Sign in to track items.');
      }
      return createListingWatch({
        userId: session.user.id,
        listingId: listing.id,
        source: listing.source,
        name: listing.title,
      });
    },
  });

  return (
    <View style={styles.previewContainer}>
      {imageUrl && <Image source={{ uri: imageUrl }} style={styles.previewImage} contentFit="cover" />}

      <Text variant="large" numberOfLines={2}>
        {listing.title}
      </Text>
      <Text variant="muted">{currencyFormatter.format(listing.price)}</Text>

      <SourceBadge source={listing.source} />

      {chips.length > 0 && (
        <View style={styles.chipRow}>
          {chips.map((chip) => (
            <Chip key={chip} label={chip} />
          ))}
        </View>
      )}

      <TrustBadge seller={listing.seller} />

      {trackMutation.isError && (
        <Text className="text-destructive" variant="small">
          {trackMutation.error instanceof Error
            ? trackMutation.error.message
            : "Couldn't track this item."}
        </Text>
      )}
      {trackMutation.isSuccess && <Text variant="muted">Tracking this item.</Text>}

      <View style={styles.previewButtonRow}>
        <Button
          variant="outline"
          className="flex-1"
          onPress={() => {
            Linking.openURL(listing.url);
            onDismiss();
          }}>
          <Text>View</Text>
        </Button>
        <Button
          className="flex-1"
          disabled={trackMutation.isPending || trackMutation.isSuccess}
          onPress={() => trackMutation.mutate()}>
          <Text>{trackMutation.isSuccess ? 'Tracking' : trackMutation.isPending ? 'Tracking…' : 'Track'}</Text>
        </Button>
      </View>
    </View>
  );
}

function SourceBadge({ source }: { source: string }) {
  const theme = useTheme();
  return (
    <ThemedText type="small" style={{ color: theme.textSecondary, fontWeight: '600' }}>
      {SOURCE_LABELS[source] ?? source}
    </ThemedText>
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
  },
  cardRow: {
    flexDirection: 'row',
    gap: Spacing.three,
  },
  thumbnail: {
    width: 72,
    height: 72,
    borderRadius: Spacing.two,
  },
  cardContent: {
    flex: 1,
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
    gap: Spacing.two,
  },
  subtitle: {
    flex: 1,
  },
  discoveryNote: {
    fontStyle: 'italic',
  },
  previewContainer: {
    width: 280,
    padding: Spacing.three,
    gap: Spacing.two,
  },
  previewImage: {
    width: '100%',
    height: 140,
    borderRadius: Spacing.two,
  },
  previewButtonRow: {
    flexDirection: 'row',
    gap: Spacing.two,
    marginTop: Spacing.one,
  },
});
