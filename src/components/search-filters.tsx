import { useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, TextInput, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { SearchFilters as SearchFiltersType } from '@/lib/api-client';
import { useTheme } from '@/hooks/use-theme';

const RADIUS_OPTIONS = [10, 25, 50, 100];
const DRIVETRAIN_OPTIONS: { label: string; value: SearchFiltersType['drivetrain'] }[] = [
  { label: 'Any', value: undefined },
  { label: 'RWD', value: 'RWD' },
  { label: 'AWD', value: 'AWD' },
];

function OptionPill({
  label,
  selected,
  onPress,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
}) {
  const theme = useTheme();
  return (
    <Pressable
      onPress={onPress}
      style={[
        styles.pill,
        {
          backgroundColor: selected ? theme.primary : theme.backgroundElement,
          borderColor: selected ? theme.primary : theme.backgroundSelected,
        },
      ]}>
      <ThemedText
        type="small"
        style={{ color: selected ? theme.onPrimary : theme.text, fontWeight: '600' }}>
        {label}
      </ThemedText>
    </Pressable>
  );
}

export function SearchFiltersForm({
  value,
  onSubmit,
  isLoading,
}: {
  value: SearchFiltersType;
  onSubmit: (filters: SearchFiltersType) => void;
  isLoading?: boolean;
}) {
  const theme = useTheme();
  const [draft, setDraft] = useState(value);

  return (
    <View style={styles.container}>
      <View style={styles.row}>
        <View style={styles.zipField}>
          <ThemedText type="small" themeColor="textSecondary">
            Zip code
          </ThemedText>
          <TextInput
            value={draft.zip}
            onChangeText={(text) => setDraft((prev) => ({ ...prev, zip: text }))}
            keyboardType="number-pad"
            maxLength={5}
            placeholder="02026"
            placeholderTextColor={theme.textSecondary}
            style={[styles.input, { color: theme.text, borderColor: theme.backgroundSelected }]}
          />
        </View>

        <View style={styles.yearField}>
          <ThemedText type="small" themeColor="textSecondary">
            Year
          </ThemedText>
          <TextInput
            value={draft.year ? String(draft.year) : ''}
            onChangeText={(text) =>
              setDraft((prev) => ({ ...prev, year: text ? Number(text) : undefined }))
            }
            keyboardType="number-pad"
            maxLength={4}
            placeholder="Any"
            placeholderTextColor={theme.textSecondary}
            style={[styles.input, { color: theme.text, borderColor: theme.backgroundSelected }]}
          />
        </View>
      </View>

      <ThemedText type="small" themeColor="textSecondary">
        Radius
      </ThemedText>
      <View style={styles.pillRow}>
        {RADIUS_OPTIONS.map((radius) => (
          <OptionPill
            key={radius}
            label={`${radius} mi`}
            selected={draft.range === radius}
            onPress={() => setDraft((prev) => ({ ...prev, range: radius }))}
          />
        ))}
      </View>

      <ThemedText type="small" themeColor="textSecondary">
        Drivetrain
      </ThemedText>
      <View style={styles.pillRow}>
        {DRIVETRAIN_OPTIONS.map((option) => (
          <OptionPill
            key={option.label}
            label={option.label}
            selected={draft.drivetrain === option.value}
            onPress={() => setDraft((prev) => ({ ...prev, drivetrain: option.value }))}
          />
        ))}
      </View>

      <Pressable
        disabled={isLoading}
        onPress={() => onSubmit(draft)}
        style={({ pressed }) => [
          styles.searchButton,
          { backgroundColor: theme.primary, opacity: pressed || isLoading ? 0.7 : 1 },
        ]}>
        {isLoading ? (
          <ActivityIndicator color={theme.onPrimary} />
        ) : (
          <ThemedText type="default" style={{ color: theme.onPrimary, fontWeight: '700' }}>
            Search
          </ThemedText>
        )}
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: Spacing.two,
  },
  row: {
    flexDirection: 'row',
    gap: Spacing.three,
  },
  zipField: {
    flex: 1,
    gap: Spacing.half,
  },
  yearField: {
    width: 90,
    gap: Spacing.half,
  },
  input: {
    borderWidth: 1,
    borderRadius: Spacing.two,
    paddingHorizontal: Spacing.two,
    paddingVertical: Spacing.two,
    fontSize: 16,
  },
  pillRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.one,
  },
  pill: {
    borderWidth: 1,
    borderRadius: Spacing.five,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.one,
  },
  searchButton: {
    marginTop: Spacing.one,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: Spacing.five,
    paddingVertical: Spacing.two,
  },
});
