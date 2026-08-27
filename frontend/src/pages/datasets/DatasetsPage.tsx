import { Badge, Button, Table, Text } from "@chakra-ui/react";
import { Upload } from "lucide-react";
import { SurfaceCard } from "@/components/ui/SurfaceCard";
import { SplitBar } from "@/components/ui/SplitBar";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { useDatasets, useSendToRoboflow } from "@/hooks/useDatasets";
import { formatBytes, formatDateTime, formatDuration, formatNumber } from "@/lib/format";
import type { RoboflowStatus } from "@/types/api";

const ROBOFLOW_LABEL: Record<RoboflowStatus, { text: string; palette: string }> = {
  never_sent: { text: "nunca enviado", palette: "gray" },
  queued: { text: "na fila", palette: "blue" },
  uploading: { text: "enviando", palette: "blue" },
  sent: { text: "enviado", palette: "green" },
  failed: { text: "falhou", palette: "red" },
};

export function DatasetsPage() {
  const datasets = useDatasets();
  const send = useSendToRoboflow();

  if (datasets.isLoading) return <LoadingState />;
  if (datasets.isError)
    return <ErrorState error={datasets.error} onRetry={() => datasets.refetch()} />;

  const items = datasets.data?.items ?? [];
  const totalImages = items.reduce((sum, item) => sum + item.image_count, 0);

  return (
    <SurfaceCard
      title={`Datasets · ${items.length} versão(ões) · ${formatNumber(totalImages)} imagens`}
    >
      {items.length === 0 ? (
        <EmptyState
          title="Nenhuma coleta salva"
          description="Inicie uma coleta na página Voo. Ao salvar, ela vira uma versão aqui, já particionada."
        />
      ) : (
        <Table.Root size="sm" variant="line" interactive>
          <Table.Header>
            <Table.Row>
              <Table.ColumnHeader>Versão</Table.ColumnHeader>
              <Table.ColumnHeader>Data</Table.ColumnHeader>
              <Table.ColumnHeader>Duração</Table.ColumnHeader>
              <Table.ColumnHeader textAlign="end">Imagens</Table.ColumnHeader>
              <Table.ColumnHeader>Distribuição</Table.ColumnHeader>
              <Table.ColumnHeader>Disco</Table.ColumnHeader>
              <Table.ColumnHeader>Roboflow</Table.ColumnHeader>
              <Table.ColumnHeader />
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {items.map((dataset) => {
              const badge = ROBOFLOW_LABEL[dataset.roboflow_status];
              const busy = send.isPending && send.variables === dataset.id;

              return (
                <Table.Row key={dataset.id}>
                  <Table.Cell>
                    <Text textStyle="readout" fontWeight="700" color="accent.solid">
                      {dataset.version}
                    </Text>
                  </Table.Cell>
                  <Table.Cell>
                    <Text textStyle="readout" fontSize="sm">
                      {formatDateTime(dataset.started_at)}
                    </Text>
                  </Table.Cell>
                  <Table.Cell>
                    <Text textStyle="readout" fontSize="sm" color="fg.muted">
                      {formatDuration(dataset.duration_seconds)}
                    </Text>
                  </Table.Cell>
                  <Table.Cell textAlign="end">
                    <Text textStyle="readout" fontSize="sm" fontWeight="700">
                      {formatNumber(dataset.image_count)}
                    </Text>
                  </Table.Cell>
                  <Table.Cell>
                    <SplitBar distribution={dataset.distribution} total={dataset.image_count} />
                  </Table.Cell>
                  <Table.Cell>
                    <Text textStyle="readout" fontSize="sm" color="fg.muted">
                      {formatBytes(dataset.disk_bytes)}
                    </Text>
                  </Table.Cell>
                  <Table.Cell>
                    <Badge colorPalette={badge.palette} variant="subtle" size="sm">
                      {badge.text}
                    </Badge>
                  </Table.Cell>
                  <Table.Cell textAlign="end">
                    <Button
                      size="xs"
                      variant="outline"
                      loading={busy}
                      disabled={dataset.status !== "saved"}
                      onClick={() => send.mutate(dataset.id)}
                    >
                      <Upload size={14} /> Enviar Roboflow
                    </Button>
                  </Table.Cell>
                </Table.Row>
              );
            })}
          </Table.Body>
        </Table.Root>
      )}
    </SurfaceCard>
  );
}
