import { Flex, Grid, GridItem, Table, Text } from "@chakra-ui/react";
import { SurfaceCard } from "@/components/ui/SurfaceCard";
import { DemoBadge } from "@/components/ui/DemoBadge";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { TimeSeriesChart } from "@/components/charts/TimeSeriesChart";
import { DamageRatioChart } from "@/components/charts/DamageRatioChart";
import { useInspectionStatistics, useInspectionTrend, useInspections } from "@/hooks/useInspections";
import { formatDate, formatDuration } from "@/lib/format";

export function InspectionsPage() {
  const trend = useInspectionTrend("count");
  const stats = useInspectionStatistics();
  const list = useInspections();

  return (
    <Grid templateColumns={{ base: "1fr", xl: "minmax(0, 1.7fr) minmax(0, 1fr)" }} gap={6}>
      <GridItem>
        <SurfaceCard title="Evolução das inspeções">
          {trend.isLoading && <LoadingState />}
          {trend.isError && <ErrorState error={trend.error} onRetry={() => trend.refetch()} />}
          {trend.data && <TimeSeriesChart data={trend.data} valueLabel="inspeções" height={260} />}
        </SurfaceCard>
      </GridItem>

      <GridItem>
        <SurfaceCard title="Inspeções com avarias">
          {stats.isLoading && <LoadingState />}
          {stats.isError && <ErrorState error={stats.error} onRetry={() => stats.refetch()} />}
          {stats.data && <DamageRatioChart stats={stats.data} />}
        </SurfaceCard>
      </GridItem>

      <GridItem colSpan={{ base: 1, xl: 2 }}>
        <SurfaceCard title="Tabela de inspeções">
          {list.isLoading && <LoadingState />}
          {list.isError && <ErrorState error={list.error} onRetry={() => list.refetch()} />}
          {list.data?.items.length === 0 && (
            <EmptyState title="Nenhuma inspeção processada até agora" />
          )}
          {list.data && list.data.items.length > 0 && (
            <Table.Root size="sm" variant="line" interactive>
              <Table.Header>
                <Table.Row>
                  <Table.ColumnHeader>Inspeção</Table.ColumnHeader>
                  <Table.ColumnHeader>Data</Table.ColumnHeader>
                  <Table.ColumnHeader>Tempo de voo</Table.ColumnHeader>
                  <Table.ColumnHeader textAlign="end">Quantidade de avarias</Table.ColumnHeader>
                </Table.Row>
              </Table.Header>
              <Table.Body>
                {list.data.items.map((inspection) => (
                  <Table.Row key={inspection.id}>
                    <Table.Cell>
                      <Flex align="center" gap={2}>
                        <Text textStyle="readout" fontSize="sm" fontWeight="700">
                          {inspection.code}
                        </Text>
                        <DemoBadge source={inspection.source} />
                      </Flex>
                    </Table.Cell>
                    <Table.Cell>
                      <Text textStyle="readout" fontSize="sm">
                        {formatDate(inspection.inspected_at)}
                      </Text>
                    </Table.Cell>
                    <Table.Cell>
                      <Text textStyle="readout" fontSize="sm" color="fg.muted">
                        {formatDuration(inspection.flight_time_seconds)}
                      </Text>
                    </Table.Cell>
                    <Table.Cell textAlign="end">
                      <Text
                        textStyle="readout"
                        fontSize="sm"
                        fontWeight="700"
                        color={inspection.damage_count > 0 ? "signal.warn" : "fg.muted"}
                      >
                        {inspection.damage_count}
                      </Text>
                    </Table.Cell>
                  </Table.Row>
                ))}
              </Table.Body>
            </Table.Root>
          )}
        </SurfaceCard>
      </GridItem>
    </Grid>
  );
}
