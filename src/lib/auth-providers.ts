import * as AppleAuthentication from 'expo-apple-authentication';
import { getQueryParams } from 'expo-auth-session/build/QueryParams';
import * as Linking from 'expo-linking';
import * as WebBrowser from 'expo-web-browser';

import { supabase } from '@/lib/supabase';

WebBrowser.maybeCompleteAuthSession();

/**
 * Apple is the seller-of-record trust badge case in the Snag data model, but
 * here it's just the native "Sign in with Apple" flow: exchange Apple's
 * identityToken directly for a Supabase session, no browser hop needed.
 */
export async function signInWithApple() {
  const credential = await AppleAuthentication.signInAsync({
    requestedScopes: [
      AppleAuthentication.AppleAuthenticationScope.FULL_NAME,
      AppleAuthentication.AppleAuthenticationScope.EMAIL,
    ],
  });

  if (!credential.identityToken) {
    throw new Error('Apple sign-in did not return an identity token.');
  }

  const { data, error } = await supabase.auth.signInWithIdToken({
    provider: 'apple',
    token: credential.identityToken,
  });
  if (error) throw error;

  // Apple only sends the name on the very first authorization ever, so
  // capture it into user metadata now or it's gone for good.
  if (credential.fullName?.givenName || credential.fullName?.familyName) {
    await supabase.auth.updateUser({
      data: {
        full_name: [credential.fullName.givenName, credential.fullName.familyName]
          .filter(Boolean)
          .join(' '),
      },
    });
  }

  return data.session;
}

/**
 * No native Google OAuth client is configured yet, so this goes through
 * Supabase's browser-based OAuth (signInWithOAuth -> system browser ->
 * redirect back into the app via the `snag://` scheme) instead of the
 * native Google Sign-In SDK. Swap to the native flow once
 * EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID exists, if a fully native picker is
 * wanted later — this flow keeps working either way.
 */
export async function signInWithGoogle() {
  const redirectTo = Linking.createURL('auth/callback');

  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: { redirectTo, skipBrowserRedirect: true },
  });
  if (error) throw error;
  if (!data.url) throw new Error('Supabase did not return an OAuth URL.');

  const result = await WebBrowser.openAuthSessionAsync(data.url, redirectTo);
  if (result.type !== 'success') {
    return null;
  }

  return createSessionFromUrl(result.url);
}

async function createSessionFromUrl(url: string) {
  const { params, errorCode } = getQueryParams(url);
  if (errorCode) throw new Error(errorCode);

  const { code, access_token, refresh_token } = params;

  if (code) {
    const { data, error } = await supabase.auth.exchangeCodeForSession(code);
    if (error) throw error;
    return data.session;
  }

  if (access_token && refresh_token) {
    const { data, error } = await supabase.auth.setSession({ access_token, refresh_token });
    if (error) throw error;
    return data.session;
  }

  return null;
}
