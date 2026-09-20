import { Image } from 'expo-image';
import { router } from 'expo-router';
import { Pressable, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

export default function LandingScreen() {
  const theme = useTheme();

  return (
    <ThemedView style={styles.container}>
      <SafeAreaView style={styles.safeArea}>
        <ThemedView style={styles.hero}>
          <Image
            style={styles.icon}
            source={require('@/assets/images/icon.png')}
            contentFit="contain"
          />
          <ThemedText type="title" style={[styles.wordmark, { color: theme.primary }]}>
            SNAG
          </ThemedText>
          <ThemedText type="subtitle" style={styles.tagline}>
            Tell it what you want.{'\n'}It tells you when it shows up.
          </ThemedText>
          <ThemedText type="small" themeColor="textSecondary" style={styles.blurb}>
            Search once across Tesla, eBay, and more. Snag watches for you and pushes a
            notification the moment a match appears.
          </ThemedText>
        </ThemedView>

        <Pressable
          onPress={() => router.push('/sign-in')}
          style={({ pressed }) => [
            styles.cta,
            { backgroundColor: theme.primary, opacity: pressed ? 0.85 : 1 },
          ]}>
          <ThemedText type="default" style={{ color: theme.onPrimary, fontWeight: '700' }}>
            Get Started
          </ThemedText>
        </Pressable>
      </SafeAreaView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
  },
  safeArea: {
    flex: 1,
    width: '100%',
    maxWidth: MaxContentWidth,
    paddingHorizontal: Spacing.four,
    paddingBottom: Spacing.four,
    justifyContent: 'space-between',
  },
  hero: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.three,
  },
  icon: {
    width: 88,
    height: 88,
    borderRadius: Spacing.three,
  },
  wordmark: {
    letterSpacing: 2,
  },
  tagline: {
    textAlign: 'center',
  },
  blurb: {
    textAlign: 'center',
    paddingHorizontal: Spacing.three,
  },
  cta: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: Spacing.three,
    borderRadius: Spacing.five,
  },
});
