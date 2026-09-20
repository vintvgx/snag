import { ActivityIndicator, StyleSheet } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

/**
 * Bridges the gap between the native splash screen disappearing and the
 * auth session query resolving, so there's never a blank frame or a flash
 * of the wrong screen (landing vs. tabs) while we don't yet know if the
 * user has a session.
 */
export function LoadingScreen() {
  const theme = useTheme();

  return (
    <ThemedView style={styles.container}>
      <ActivityIndicator size="large" color={theme.primary} />
      <ThemedText type="smallBold" themeColor="textSecondary">
        SNAG
      </ThemedText>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.three,
  },
});
