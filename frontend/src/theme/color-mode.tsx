/**
 * Modo claro/escuro. O Chakra v3 delega a persistência ao `next-themes`,
 * que funciona igual fora do Next.
 *
 * O padrão é o claro (a referência Purity é clara). O escuro existe porque a
 * página Voo é usada em campo, muitas vezes em cabine ou à noite.
 */
import { ThemeProvider, useTheme } from "next-themes";
import type { PropsWithChildren } from "react";

export function ColorModeProvider({ children }: PropsWithChildren) {
  return (
    <ThemeProvider attribute="class" disableTransitionOnChange defaultTheme="light">
      {children}
    </ThemeProvider>
  );
}

export function useColorMode() {
  const { resolvedTheme, setTheme } = useTheme();
  return {
    colorMode: resolvedTheme,
    isDark: resolvedTheme === "dark",
    toggleColorMode: () => setTheme(resolvedTheme === "dark" ? "light" : "dark"),
  };
}
