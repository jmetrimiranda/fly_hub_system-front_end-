/**
 * Design system do FlyHub.
 *
 * A referência visual é o Purity UI (Chakra): fundo claro e frio, cards brancos
 * com sombra difusa, cantos generosos, acento em teal. O que este tema
 * acrescenta é a leitura de painel de instrumento, que o produto pede: valores
 * de telemetria em fonte monoespaçada com algarismos tabulares — o número não
 * "pula" quando o bitrate oscila — e rótulos em versalete estreito.
 *
 * Toda cor e todo tamanho saem daqui. Componente com hex escrito na mão não
 * passa em revisão.
 */
import { createSystem, defaultConfig, defineConfig } from "@chakra-ui/react";

const config = defineConfig({
  globalCss: {
    "html, body": {
      bg: "bg.canvas",
      color: "fg.default",
      fontFeatureSettings: '"cv11", "ss01"',
    },
    "*::selection": { bg: "brand.100" },
    // Acessibilidade: quem pede menos movimento não recebe o voo do drone.
    // O seletor vem antes da media query — Chakra tipa o interior de um `@media`
    // como propriedades de estilo, não como um novo nível de seletores.
    "*": {
      "@media (prefers-reduced-motion: reduce)": {
        animationDuration: "0.01ms !important",
        transitionDuration: "0.01ms !important",
      },
    },
  },
  theme: {
    tokens: {
      fonts: {
        heading: { value: "'Plus Jakarta Sans', system-ui, sans-serif" },
        body: { value: "'Plus Jakarta Sans', system-ui, sans-serif" },
        mono: { value: "'JetBrains Mono', ui-monospace, monospace" },
      },
      colors: {
        brand: {
          50: { value: "#E6FAF8" },
          100: { value: "#C2F2ED" },
          200: { value: "#8FE6DE" },
          300: { value: "#57D6CB" },
          400: { value: "#2FC4B8" },
          500: { value: "#14A89D" },
          600: { value: "#0F8A81" },
          700: { value: "#0B6B64" },
          800: { value: "#084F4A" },
          900: { value: "#053331" },
        },
        // Cores de sinal: as mesmas semânticas do LED físico de um rack.
        signal: {
          live: { value: "#22C55E" },
          down: { value: "#EF4444" },
          warn: { value: "#F59E0B" },
          idle: { value: "#64748B" },
        },
        ink: {
          50: { value: "#F4F7FE" },
          100: { value: "#E7ECF6" },
          200: { value: "#CBD5E1" },
          400: { value: "#94A3B8" },
          600: { value: "#475569" },
          800: { value: "#1E293B" },
          900: { value: "#0F172A" },
          950: { value: "#080F1F" },
        },
      },
      radii: {
        card: { value: "18px" },
        control: { value: "12px" },
      },
      shadows: {
        card: { value: "0 18px 40px -24px rgba(15, 23, 42, 0.28)" },
        raised: { value: "0 24px 48px -20px rgba(15, 23, 42, 0.34)" },
      },
    },
    semanticTokens: {
      colors: {
        "bg.canvas": { value: { base: "{colors.ink.50}", _dark: "{colors.ink.950}" } },
        "bg.surface": { value: { base: "white", _dark: "{colors.ink.900}" } },
        "bg.subtle": { value: { base: "{colors.ink.100}", _dark: "{colors.ink.800}" } },
        "bg.viewer": { value: { base: "{colors.ink.900}", _dark: "#04070F" } },
        "fg.default": { value: { base: "{colors.ink.900}", _dark: "{colors.ink.50}" } },
        "fg.muted": { value: { base: "{colors.ink.600}", _dark: "{colors.ink.400}" } },
        "fg.faint": { value: { base: "{colors.ink.400}", _dark: "{colors.ink.600}" } },
        "border.subtle": { value: { base: "{colors.ink.100}", _dark: "{colors.ink.800}" } },
        "accent.solid": { value: { base: "{colors.brand.500}", _dark: "{colors.brand.400}" } },
      },
    },
    textStyles: {
      // Rótulo de instrumento: pequeno, espaçado, sem peso demais.
      label: {
        value: {
          fontSize: "11px",
          fontWeight: "600",
          letterSpacing: "0.09em",
          textTransform: "uppercase",
          color: "fg.muted",
        },
      },
      // Leitura de telemetria: mono com algarismos tabulares.
      readout: {
        value: {
          fontFamily: "mono",
          fontVariantNumeric: "tabular-nums",
          fontWeight: "500",
          letterSpacing: "-0.01em",
        },
      },
    },
  },
});

export const system = createSystem(defaultConfig, config);
