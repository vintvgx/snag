import { useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, TextInput, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

// MVP seed items (see CLAUDE.md "Focus pivot") — tapping one searches
// instantly without typing, and matches queries already run/cached so
// reviewing this screen doesn't burn extra SerpApi calls.
const SUGGESTIONS = ['Fujifilm GA645', 'Ray-Ban RX3717V'];

export function SearchBar({
  value,
  onSubmit,
  isLoading,
}: {
  value: string;
  onSubmit: (query: string) => void;
  isLoading?: boolean;
}) {
  const theme = useTheme();
  const [draft, setDraft] = useState(value);

  const submit = (query: string) => {
    const trimmed = query.trim();
    if (trimmed) {
      onSubmit(trimmed);
    }
  };

  return (
    <View style={styles.container}>
      <View style={[styles.inputRow, { borderColor: theme.backgroundSelected }]}>
        <TextInput
          value={draft}
          onChangeText={setDraft}
          onSubmitEditing={() => submit(draft)}
          returnKeyType="search"
          autoCorrect={false}
          placeholder="Search for an item…"
          placeholderTextColor={theme.textSecondary}
          style={[styles.input, { color: theme.text }]}
        />
        <Pressable
          disabled={isLoading}
          onPress={() => submit(draft)}
          style={({ pressed }) => [
            styles.searchButton,
            { backgroundColor: theme.primary, opacity: pressed || isLoading ? 0.7 : 1 },
          ]}>
          {isLoading ? (
            <ActivityIndicator color={theme.onPrimary} />
          ) : (
            <ThemedText type="small" style={{ color: theme.onPrimary, fontWeight: '700' }}>
              Search
            </ThemedText>
          )}
        </Pressable>
      </View>

      <View style={styles.suggestionRow}>
        {SUGGESTIONS.map((suggestion) => (
          <Pressable
            key={suggestion}
            onPress={() => {
              setDraft(suggestion);
              submit(suggestion);
            }}
            style={[styles.suggestionPill, { borderColor: theme.backgroundSelected }]}>
            <ThemedText type="small" themeColor="textSecondary">
              {suggestion}
            </ThemedText>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: Spacing.two,
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
    borderWidth: 1,
    borderRadius: Spacing.five,
    paddingLeft: Spacing.three,
    paddingRight: Spacing.one,
    paddingVertical: Spacing.one,
  },
  input: {
    flex: 1,
    fontSize: 16,
    paddingVertical: Spacing.one,
  },
  searchButton: {
    borderRadius: Spacing.five,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.two,
    alignItems: 'center',
    justifyContent: 'center',
  },
  suggestionRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.one,
  },
  suggestionPill: {
    borderWidth: 1,
    borderRadius: Spacing.five,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.one,
  },
});
