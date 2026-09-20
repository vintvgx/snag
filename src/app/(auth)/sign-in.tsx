import * as AppleAuthentication from 'expo-apple-authentication';
import { router } from 'expo-router';
import { ActivityIndicator, Platform, Pressable, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, Spacing } from '@/constants/theme';
import { useAuth } from '@/contexts/auth-context';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { useTheme } from '@/hooks/use-theme';

export default function SignInScreen() {
  const theme = useTheme();
  const colorScheme = useColorScheme();
  const { signInWithApple, signInWithGoogle, isSigningIn, error } = useAuth();

  return (
    <ThemedView style={styles.container}>
      <SafeAreaView style={styles.safeArea}>
        {router.canGoBack() && (
          <Pressable onPress={() => router.back()} hitSlop={Spacing.two}>
            <ThemedText type="link" themeColor="textSecondary">
              ‹ Back
            </ThemedText>
          </Pressable>
        )}

        <ThemedView style={styles.body}>
          <ThemedText type="subtitle">Sign in to Snag</ThemedText>
          <ThemedText type="small" themeColor="textSecondary" style={styles.subtext}>
            We only use this to save your watches and send you match notifications.
          </ThemedText>

          <ThemedView style={styles.buttons}>
            {Platform.OS === 'ios' && (
              <AppleAuthentication.AppleAuthenticationButton
                buttonType={AppleAuthentication.AppleAuthenticationButtonType.SIGN_IN}
                buttonStyle={
                  colorScheme === 'dark'
                    ? AppleAuthentication.AppleAuthenticationButtonStyle.WHITE
                    : AppleAuthentication.AppleAuthenticationButtonStyle.BLACK
                }
                cornerRadius={Spacing.two}
                style={styles.appleButton}
                onPress={() => signInWithApple().catch(() => {})}
              />
            )}

            <Pressable
              disabled={isSigningIn}
              onPress={() => signInWithGoogle().catch(() => {})}
              style={({ pressed }) => [
                styles.googleButton,
                { borderColor: theme.textSecondary, opacity: pressed || isSigningIn ? 0.6 : 1 },
              ]}>
              <ThemedText type="default" style={styles.googleButtonText}>
                Continue with Google
              </ThemedText>
            </Pressable>
          </ThemedView>

          {isSigningIn && <ActivityIndicator color={theme.primary} />}
          {error && (
            <ThemedText type="small" themeColor="primary" style={styles.error}>
              {error.message}
            </ThemedText>
          )}
        </ThemedView>
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
    paddingTop: Spacing.three,
    justifyContent: 'space-between',
  },
  body: {
    flex: 1,
    justifyContent: 'center',
    gap: Spacing.three,
  },
  subtext: {
    marginBottom: Spacing.two,
  },
  buttons: {
    gap: Spacing.three,
    marginTop: Spacing.three,
  },
  appleButton: {
    width: '100%',
    height: 50,
  },
  googleButton: {
    height: 50,
    borderRadius: Spacing.two,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  googleButtonText: {
    fontWeight: '600',
  },
  error: {
    textAlign: 'center',
    marginTop: Spacing.three,
  },
});
