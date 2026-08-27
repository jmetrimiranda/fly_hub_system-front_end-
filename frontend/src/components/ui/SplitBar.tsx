import { Box, Flex, Text } from "@chakra-ui/react";
import type { SplitDistribution } from "@/types/api";

const SEGMENTS = [
  { key: "train", label: "train", color: "brand.500" },
  { key: "valid", label: "valid", color: "brand.300" },
  { key: "test", label: "test", color: "signal.warn" },
] as const;

/**
 * Barra da divisão train/valid/test.
 *
 * Mostra também os frames em embargo — os que caíram na faixa descartada entre
 * blocos. Esconder esse número faria a soma não bater com o total de imagens,
 * e alguém perderia uma tarde procurando o erro.
 */
export function SplitBar({ distribution, total }: { distribution: SplitDistribution; total: number }) {
  const assigned = distribution.train + distribution.valid + distribution.test;
  const embargoed = Math.max(0, total - assigned);
  const denominator = Math.max(1, total);

  return (
    <Box minW="180px">
      <Flex h="7px" rounded="full" overflow="hidden" bg="bg.subtle" gap="1px">
        {SEGMENTS.map((segment) => (
          <Box
            key={segment.key}
            bg={segment.color}
            w={`${(distribution[segment.key] / denominator) * 100}%`}
          />
        ))}
        {embargoed > 0 && <Box bg="fg.faint" w={`${(embargoed / denominator) * 100}%`} />}
      </Flex>
      <Text textStyle="readout" fontSize="11px" color="fg.muted" mt={1.5}>
        {distribution.train} / {distribution.valid} / {distribution.test}
        {embargoed > 0 && ` · ${embargoed} em embargo`}
      </Text>
    </Box>
  );
}
