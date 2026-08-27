import { Box, Flex, Text } from "@chakra-ui/react";
import type { ReactNode } from "react";
import { StatusDot } from "./StatusDot";

interface Props {
  label: string;
  value: ReactNode;
  unit?: string;
  icon?: ReactNode;
  status?: "live" | "down" | "warn" | "idle";
  hint?: string;
  loading?: boolean;
}

/**
 * Card de indicador. O valor é monoespaçado e tabular: quando o número muda
 * sozinho, ele não empurra o resto da linha.
 */
export function StatCard({ label, value, unit, icon, status, hint, loading }: Props) {
  return (
    <Box
      bg="bg.surface"
      rounded="card"
      shadow="card"
      borderWidth="1px"
      borderColor="border.subtle"
      px={5}
      py={4}
      transition="box-shadow 160ms ease, transform 160ms ease"
      _hover={{ shadow: "raised", transform: "translateY(-1px)" }}
    >
      <Flex align="center" justify="space-between" gap={3}>
        <Box minW={0}>
          <Flex align="center" gap={2} mb={1}>
            {status && <StatusDot tone={status} />}
            <Text textStyle="label" truncate>
              {label}
            </Text>
          </Flex>
          <Flex align="baseline" gap={1}>
            <Text
              textStyle="readout"
              fontSize="2xl"
              lineHeight="1.15"
              opacity={loading ? 0.35 : 1}
              truncate
            >
              {loading ? "—" : value}
            </Text>
            {unit && (
              <Text textStyle="readout" fontSize="sm" color="fg.muted">
                {unit}
              </Text>
            )}
          </Flex>
          {hint && (
            <Text fontSize="xs" color="fg.faint" mt={1} truncate>
              {hint}
            </Text>
          )}
        </Box>
        {icon && (
          <Flex
            align="center"
            justify="center"
            w="44px"
            h="44px"
            rounded="control"
            bg="accent.solid"
            color="white"
            flexShrink={0}
          >
            {icon}
          </Flex>
        )}
      </Flex>
    </Box>
  );
}
