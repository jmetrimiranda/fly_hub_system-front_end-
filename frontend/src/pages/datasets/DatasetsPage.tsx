import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Button, Flex, Input, Table, Text } from "@chakra-ui/react";
import { ChevronRight, Trash2 } from "lucide-react";
import { SurfaceCard } from "@/components/ui/SurfaceCard";
import { SplitBar } from "@/components/ui/SplitBar";
import { DemoBadge } from "@/components/ui/DemoBadge";
import { Modal } from "@/components/ui/Modal";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { useDatasets } from "@/hooks/useDatasets";
import { useClearDemoData, useDemoData } from "@/hooks/useDemoData";
import { formatBytes, formatDateTime, formatDuration, formatNumber } from "@/lib/format";
import type { RoboflowStatus } from "@/types/api";

/** O operador digita isto para confirmar. Ver o modal, mais abaixo. */
const CONFIRM_PHRASE = "remover demonstração";

const ROBOFLOW_LABEL: Record<RoboflowStatus, { text: string; palette: string }> = {
  never_sent: { text: "nunca enviado", palette: "gray" },
  queued: { text: "na fila", palette: "blue" },
  uploading: { text: "enviando", palette: "blue" },
  sent: { text: "enviado", palette: "green" },
  failed: { text: "falhou", palette: "red" },
};

export function DatasetsPage() {
  const datasets = useDatasets();
  const demo = useDemoData();
  const clearDemo = useClearDemoData();
  const navigate = useNavigate();

  const [clearing, setClearing] = useState(false);
  const [typed, setTyped] = useState("");

  if (datasets.isLoading) return <LoadingState />;
  if (datasets.isError)
    return <ErrorState error={datasets.error} onRetry={() => datasets.refetch()} />;

  const items = datasets.data?.items ?? [];
  const totalImages = items.reduce((sum, item) => sum + item.image_count, 0);
  // O botão só aparece havendo o que remover: numa instalação que já saiu da
  // demonstração ele seria um botão perigoso sem função.
  const demoTotal =
    (demo.data?.datasets ?? 0) +
    (demo.data?.inspections ?? 0) +
    (demo.data?.model_metrics ?? 0) +
    (demo.data?.sap_notes ?? 0);

  const closeClearing = () => {
    setClearing(false);
    setTyped("");
  };

  return (
    <>
    <SurfaceCard
      title={`Datasets · ${items.length} versão(ões) · ${formatNumber(totalImages)} imagens`}
      action={
        demoTotal > 0 && (
          <Button
            size="xs"
            variant="outline"
            colorPalette="orange"
            onClick={() => setClearing(true)}
          >
            <Trash2 size={14} /> Remover demonstração
          </Button>
        )
      }
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

              // A linha inteira abre o detalhe: galeria, exclusão e envio moram
              // lá, onde há espaço para o modal explicar o que cada um faz.
              return (
                <Table.Row
                  key={dataset.id}
                  cursor="pointer"
                  onClick={() => navigate(`/datasets/${dataset.id}`)}
                >
                  <Table.Cell>
                    <Flex align="center" gap={2}>
                      <Text textStyle="readout" fontWeight="700" color="accent.solid">
                        {dataset.version}
                      </Text>
                      <DemoBadge source={dataset.source} />
                    </Flex>
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
                    <Button size="xs" variant="ghost" aria-label={`Abrir ${dataset.version}`}>
                      Abrir <ChevronRight size={14} />
                    </Button>
                  </Table.Cell>
                </Table.Row>
              );
            })}
          </Table.Body>
        </Table.Root>
      )}
    </SurfaceCard>

    {/* Irreversível, e atravessa três telas de uma vez: exige digitar a frase,
        do mesmo jeito que excluir um dataset exige digitar a versão. */}
    <Modal
      open={clearing}
      onClose={closeClearing}
      title="Remover os dados de demonstração?"
      confirmLabel="Remover demonstração"
      tone="danger"
      confirmDisabled={typed.trim() !== CONFIRM_PHRASE}
      confirmLoading={clearDemo.isPending}
      onConfirm={() => clearDemo.mutate(undefined, { onSuccess: closeClearing })}
    >
      <Flex direction="column" gap={3}>
        <Text fontSize="sm">
          Serão apagados {formatNumber(demo.data?.datasets ?? 0)} dataset(s),{" "}
          {formatNumber(demo.data?.inspections ?? 0)} inspeção(ões),{" "}
          {formatNumber(demo.data?.sap_notes ?? 0)} nota(s) SAP e{" "}
          {formatNumber(demo.data?.model_metrics ?? 0)} métrica(s) — tudo que o{" "}
          <code>seed.py</code> criou, e nada além disso.
        </Text>
        <Text fontSize="sm" color="fg.muted">
          As coletas de voo permanecem. A separação não é por data nem por nome: cada linha carrega
          a marca de origem desde que foi gravada.
        </Text>
        <Text fontSize="sm" color="fg.muted">
          Para confirmar, digite <b>{CONFIRM_PHRASE}</b>:
        </Text>
        <Input
          size="sm"
          value={typed}
          placeholder={CONFIRM_PHRASE}
          onChange={(event) => setTyped(event.target.value)}
        />
      </Flex>
    </Modal>
    </>
  );
}
