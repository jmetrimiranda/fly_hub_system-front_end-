import { Box } from "@chakra-ui/react";

type Tone = "live" | "down" | "warn" | "idle";

const COLOR: Record<Tone, string> = {
  live: "signal.live",
  down: "signal.down",
  warn: "signal.warn",
  idle: "signal.idle",
};

/**
 * LED de estado. O halo pulsa só quando está no ar — movimento constante em
 * uma tela de monitoramento vira ruído e as pessoas param de olhar.
 */
export function StatusDot({ tone = "idle", size = "10px" }: { tone?: Tone; size?: string }) {
  return (
    <Box
      as="span"
      display="inline-block"
      w={size}
      h={size}
      rounded="full"
      bg={COLOR[tone]}
      flexShrink={0}
      boxShadow={tone === "live" ? "0 0 0 4px rgba(34,197,94,0.18)" : undefined}
      animation={tone === "live" ? "pulse 2.4s ease-in-out infinite" : undefined}
      css={{
        "@keyframes pulse": {
          "0%, 100%": { opacity: 1 },
          "50%": { opacity: 0.55 },
        },
      }}
    />
  );
}
