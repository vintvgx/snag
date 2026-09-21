// React Navigation theme object (consumed by expo-router's <ThemeProvider>),
// built from the same ported color values as src/global.css's CSS
// variables — kept in sync manually since one is CSS, the other JS.
//
// NOT wired into src/app/_layout.tsx yet (that still uses expo-router's
// default DefaultTheme/DarkTheme) — this file exists so later work can
// switch the navigator chrome (header/tab bar) over to the app's real
// brand colors instead of RN Navigation's stock blue, without having to
// re-derive these values.
import { DarkTheme, DefaultTheme, type Theme } from 'expo-router/react-navigation';

export const THEME = {
  light: {
    background: 'hsl(0 0% 100%)',
    foreground: 'hsl(0 0% 0%)',
    card: 'hsl(240 11.1% 94.7%)',
    cardForeground: 'hsl(0 0% 0%)',
    popover: 'hsl(240 11.1% 94.7%)',
    popoverForeground: 'hsl(0 0% 0%)',
    primary: 'hsl(347 77.2% 49.8%)',
    primaryForeground: 'hsl(0 0% 100%)',
    secondary: 'hsl(240 11.1% 94.7%)',
    secondaryForeground: 'hsl(0 0% 0%)',
    muted: 'hsl(230 10.7% 89%)',
    mutedForeground: 'hsl(220 5.9% 40%)',
    accent: 'hsl(230 10.7% 89%)',
    accentForeground: 'hsl(0 0% 0%)',
    destructive: 'hsl(347 77.2% 49.8%)',
    border: 'hsl(230 10.7% 89%)',
    input: 'hsl(230 10.7% 89%)',
    ring: 'hsl(347 77.2% 49.8%)',
    radius: '1rem',
  },
  dark: {
    background: 'hsl(0 0% 0%)',
    foreground: 'hsl(0 0% 100%)',
    card: 'hsl(225 5.7% 13.7%)',
    cardForeground: 'hsl(0 0% 100%)',
    popover: 'hsl(225 5.7% 13.7%)',
    popoverForeground: 'hsl(0 0% 100%)',
    primary: 'hsl(346 96% 60.8%)',
    primaryForeground: 'hsl(0 0% 100%)',
    secondary: 'hsl(225 5.7% 13.7%)',
    secondaryForeground: 'hsl(0 0% 100%)',
    muted: 'hsl(214 7.1% 19.4%)',
    mutedForeground: 'hsl(216 6.8% 71%)',
    accent: 'hsl(214 7.1% 19.4%)',
    accentForeground: 'hsl(0 0% 100%)',
    destructive: 'hsl(346 96% 60.8%)',
    border: 'hsl(214 7.1% 19.4%)',
    input: 'hsl(214 7.1% 19.4%)',
    ring: 'hsl(346 96% 60.8%)',
    radius: '1rem',
  },
} as const;

export const NAV_THEME: Record<'light' | 'dark', Theme> = {
  light: {
    ...DefaultTheme,
    colors: {
      background: THEME.light.background,
      border: THEME.light.border,
      card: THEME.light.card,
      notification: THEME.light.destructive,
      primary: THEME.light.primary,
      text: THEME.light.foreground,
    },
  },
  dark: {
    ...DarkTheme,
    colors: {
      background: THEME.dark.background,
      border: THEME.dark.border,
      card: THEME.dark.card,
      notification: THEME.dark.destructive,
      primary: THEME.dark.primary,
      text: THEME.dark.foreground,
    },
  },
};
