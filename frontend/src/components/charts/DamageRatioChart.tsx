import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import { Box, Flex, Text } from "@chakra-ui/react";
import type { InspectionStatistics } from "@/types/api";
import { formatPercent } from "@/lib/format";
import { chartColors } from "./chartTheme";

/**
 * Proporção de inspeções com avaria.
 *
 * Anel em vez de pizza cheia: o número no centro é a resposta, e o anel só
 * dá a escala. Duas fatias não precisam de legenda.
 */
export function DamageRatioChart({ stats }: { stats: InspectionStatistics }) {
  const data = [
    { name: "Com avarias", value: stats.with_damage, color: chartColors.warn },
    { name: "Sem avarias", value: stats.without_damage, color: chartColors.line },
  ];

  return (
    <Box position="relative" height="260px">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            innerRadius="66%"
            outerRadius="88%"
            paddingAngle={2}
            startAngle={90}
            endAngle={-270}
            stroke="none"
          >
            {data.map((slice) => (
              <Cell key={slice.name} fill={slice.color} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>

      <Flex
        position="absolute"
        inset={0}
        direction="column"
        align="center"
        justify="center"
        pointerEvents="none"
      >
        <Text textStyle="readout" fontSize="3xl" lineHeight="1">
          {formatPercent(stats.damage_ratio, 0)}
        </Text>
        <Text textStyle="label" mt={1}>
          com avarias
        </Text>
        <Text fontSize="xs" color="fg.faint" mt={2}>
          {stats.with_damage} de {stats.total} inspeções
        </Text>
      </Flex>
    </Box>
  );
}
