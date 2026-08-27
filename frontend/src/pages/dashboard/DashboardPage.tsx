import { Box, Grid, GridItem, Table, Text } from "@chakra-ui/react";
import { Activity, FileWarning, Radio, Target } from "lucide-react";
import { StatCard } from "@/components/ui/StatCard";
import { SurfaceCard } from "@/components/ui/SurfaceCard";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { TimeSeriesChart } from "@/components/charts/TimeSeriesChart";
import { DroneViewer } from "@/components/drone3d/DroneViewer";
import { useDamageSeries, useDashboardSummary, useRecentInspections } from "@/hooks/useDashboard";
import { formatDate, formatDuration, formatNumber } from "@/lib/format";

export function DashboardPage() {
  const summary = useDashboardSummary();
  const inspections = useRecentInspections();
  const damages = useDamageSeries();

  const connected = summary.data?.flight_connection.connected ?? false;

  return (
    <Grid templateColumns={{ base: "1fr", xl: "minmax(0, 1.55fr) minmax(0, 1fr)" }} gap={6}>
      {/* Coluna esquerda: indicadores e histórico */}
      <GridItem>
        <Grid templateColumns={{ base: "1fr", sm: "1fr 1fr" }} gap={4} mb={6}>
          <StatCard
            label="Status conexão voo"
            value={summary.data?.flight_connection.label ?? "—"}
            status={connected ? "live" : "down"}
            icon={<Radio size={20} />}
            loading={summary.isLoading}
          />
          <StatCard
            label="Quantidade de inspeções"
            value={formatNumber(summary.data?.inspection_count.value ?? 0)}
            icon={<Activity size={20} />}
            loading={summary.isLoading}
          />
          <StatCard
            label="Notas abertas"
            value={formatNumber(summary.data?.open_notes.value ?? 0)}
            icon={<FileWarning size={20} />}
            loading={summary.isLoading}
            hint="Notas SAP pendentes de tratativa"
          />
          <StatCard
            label="MAPE"
            value={(summary.data?.mape.value ?? 0).toFixed(2)}
            unit="%"
            icon={<Target size={20} />}
            loading={summary.isLoading}
            hint="Score reportado pelo modelo de visão"
          />
        </Grid>

        <SurfaceCard title="Inspeções realizadas">
          {inspections.isLoading && <LoadingState />}
          {inspections.isError && (
            <ErrorState error={inspections.error} onRetry={() => inspections.refetch()} />
          )}
          {inspections.data?.items.length === 0 && (
            <EmptyState
              title="Nenhuma inspeção registrada"
              description="Assim que um voo for processado pelo modelo, ele aparece aqui."
            />
          )}
          {inspections.data && inspections.data.items.length > 0 && (
            <Table.Root size="sm" variant="line" interactive>
              <Table.Header>
                <Table.Row>
                  <Table.ColumnHeader>Data da inspeção</Table.ColumnHeader>
                  <Table.ColumnHeader textAlign="end">Tempo de voo</Table.ColumnHeader>
                  <Table.ColumnHeader textAlign="end">Avarias detectadas</Table.ColumnHeader>
                  <Table.ColumnHeader textAlign="end">Nota aberta</Table.ColumnHeader>
                </Table.Row>
              </Table.Header>
              <Table.Body>
                {inspections.data.items.map((row) => (
                  <Table.Row key={row.id}>
                    <Table.Cell>
                      <Text textStyle="readout" fontSize="sm">
                        {formatDate(row.inspected_at)}
                      </Text>
                    </Table.Cell>
                    <Table.Cell textAlign="end">
                      <Text textStyle="readout" fontSize="sm" color="fg.muted">
                        {formatDuration(row.flight_time_seconds)}
                      </Text>
                    </Table.Cell>
                    <Table.Cell textAlign="end">
                      <Text
                        textStyle="readout"
                        fontSize="sm"
                        fontWeight="700"
                        color={row.damage_count > 0 ? "signal.warn" : "fg.muted"}
                      >
                        {row.damage_count}
                      </Text>
                    </Table.Cell>
                    <Table.Cell textAlign="end">
                      <Text textStyle="readout" fontSize="sm" color="fg.muted">
                        {row.open_note_count}
                      </Text>
                    </Table.Cell>
                  </Table.Row>
                ))}
              </Table.Body>
            </Table.Root>
          )}
        </SurfaceCard>
      </GridItem>

      {/* Coluna direita: o drone acompanha o estado real da conexão */}
      <GridItem>
        <Box height={{ base: "320px", xl: "100%" }} minH="320px">
          <DroneViewer isFlying={connected} />
        </Box>
      </GridItem>

      <GridItem colSpan={{ base: 1, xl: 2 }}>
        <SurfaceCard title="Avarias detectadas por inspeção">
          {damages.isLoading && <LoadingState />}
          {damages.isError && <ErrorState error={damages.error} onRetry={() => damages.refetch()} />}
          {damages.data && <TimeSeriesChart data={damages.data} valueLabel="avarias" />}
        </SurfaceCard>
      </GridItem>
    </Grid>
  );
}
