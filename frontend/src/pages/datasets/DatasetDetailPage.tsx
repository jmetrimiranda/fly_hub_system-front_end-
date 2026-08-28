import { useState } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";
import { Box, Button, Flex, Grid, Input, Progress, Tabs, Text } from "@chakra-ui/react";
import { ArrowLeft, RefreshCw, Trash2, TriangleAlert, Upload, X } from "lucide-react";
import { ImageGallery } from "@/components/datasets/ImageGallery";
import { RoboflowUploadModal } from "@/components/datasets/RoboflowUploadModal";
import { Modal } from "@/components/ui/Modal";
import { SplitBar } from "@/components/ui/SplitBar";
import { StatCard } from "@/components/ui/StatCard";
import { SurfaceCard } from "@/components/ui/SurfaceCard";
import { ErrorState, LoadingState } from "@/components/ui/States";
import {
  useCancelRoboflow,
  useDataset,
  useDeleteDataset,
  useResplit,
  useRoboflowUpload,
  useSendToRoboflow,
} from "@/hooks/useDatasets";
import { formatBytes, formatDateTime, formatDuration, formatNumber } from "@/lib/format";
import type { SplitName, SplitWarning } from "@/types/api";

const SPLITS: SplitName[] = ["train", "valid", "test"];

export function DatasetDetailPage() {
  const { id } = useParams();
  const datasetId = Number(id);
  const dataset = useDataset(datasetId);
  const resplit = useResplit(datasetId);
  const remove = useDeleteDataset();
  const send = useSendToRoboflow(datasetId);
  const cancel = useCancelRoboflow(datasetId);

  const [sending, setSending] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [typed, setTyped] = useState("");

  const uploading = dataset.data?.roboflow_status === "uploading";
  const upload = useRoboflowUpload(datasetId, uploading);

  if (dataset.isLoading) return <LoadingState />;
  if (dataset.isError) return <ErrorState error={dataset.error} onRetry={() => dataset.refetch()} />;

  const data = dataset.data!;
  const counts = data.counts;

  return (
    <Flex direction="column" gap={6}>
      <Flex align="center" justify="space-between" gap={3} wrap="wrap">
        <Flex align="center" gap={3}>
          <Button asChild size="xs" variant="ghost">
            <RouterLink to="/datasets">
              <ArrowLeft size={14} /> Datasets
            </RouterLink>
          </Button>
          <Text fontSize="lg" fontWeight="700" textStyle="readout" color="accent.solid">
            {data.version}
          </Text>
        </Flex>
        <Flex gap={2}>
          <Button
            size="xs"
            variant="outline"
            loading={resplit.isPending}
            onClick={() => resplit.mutate()}
          >
            <RefreshCw size={14} /> Refazer split
          </Button>
          <Button
            size="xs"
            colorPalette="teal"
            disabled={data.status !== "saved" || uploading}
            onClick={() => setSending(true)}
          >
            <Upload size={14} /> Enviar Roboflow
          </Button>
          <Button size="xs" variant="outline" colorPalette="red" onClick={() => setDeleting(true)}>
            <Trash2 size={14} /> Excluir dataset
          </Button>
        </Flex>
      </Flex>

      <Grid templateColumns={{ base: "1fr", sm: "1fr 1fr", xl: "repeat(4, 1fr)" }} gap={4}>
        <StatCard label="Imagens" value={formatNumber(counts.total)} />
        <StatCard label="Duração" value={formatDuration(data.duration_seconds)} />
        <StatCard label="Em disco" value={formatBytes(data.disk_bytes)} />
        <StatCard label="Coletado em" value={formatDateTime(data.started_at)} />
      </Grid>

      <SurfaceCard title="Divisão temporal">
        <Flex direction="column" gap={4}>
          <SplitBar distribution={data.distribution} total={data.image_count} />
          <Text fontSize="xs" color="fg.muted">
            Blocos contíguos na ordem cronológica, com faixa de embargo nas fronteiras:{" "}
            {data.distribution.embargo_seconds} s e {data.distribution.embargo_frames} quadro(s).
            {data.split_at && ` Último split em ${formatDateTime(data.split_at)}.`} Amostragem a
            cada {data.sample_interval_seconds.toString().replace(".", ",")} s
            {data.dedup_enabled
              ? `, com ${formatNumber(data.dedup_skipped)} quadro(s) descartado(s) por repetição.`
              : ", sem deduplicação."}
          </Text>

          {data.drifted && (
            <Notice tone="signal.warn">
              As contagens em disco não batem mais com o manifesto — houve exclusão desde o último
              split. <b>Refazer split</b> reparticiona a partir de <code>raw/</code>, que é
              mantido justamente para isso — sem ele as proporções continuam sendo as de antes das
              exclusões.
            </Notice>
          )}
          {data.warnings.map((warning) => (
            <SplitWarningNotice key={warning.code} warning={warning} />
          ))}
        </Flex>
      </SurfaceCard>

      {(uploading || upload.data?.active) && upload.data && (
        <SurfaceCard title="Envio ao Roboflow">
          <Flex direction="column" gap={3}>
            <Progress.Root
              value={upload.data.total ? (upload.data.uploaded / upload.data.total) * 100 : 0}
              colorPalette="teal"
              size="sm"
            >
              <Progress.Track>
                <Progress.Range />
              </Progress.Track>
            </Progress.Root>
            <Flex justify="space-between" gap={3} wrap="wrap">
              <Text fontSize="xs" color="fg.muted">
                {formatNumber(upload.data.uploaded)} de {formatNumber(upload.data.total)} enviadas
                {upload.data.failed > 0 && ` · ${formatNumber(upload.data.failed)} falharam`}
                {upload.data.current_file && ` · ${upload.data.current_file}`}
              </Text>
              <Button
                size="xs"
                variant="outline"
                colorPalette="red"
                loading={cancel.isPending}
                onClick={() => cancel.mutate()}
              >
                <X size={14} /> Cancelar
              </Button>
            </Flex>
          </Flex>
        </SurfaceCard>
      )}

      {data.roboflow_error && (
        <Notice tone="signal.warn">
          {data.roboflow_error} Enviar de novo retoma de onde parou: o que já subiu não sobe outra
          vez.
        </Notice>
      )}

      <SurfaceCard title="Imagens originais">
        <Text fontSize="xs" color="fg.muted" mb={4}>
          Os quadros como saíram do leitor, sem inferência. A página Voo mostra a imagem
          processada; esta, nunca.
        </Text>
        <Tabs.Root defaultValue="train" variant="line">
          <Tabs.List>
            {SPLITS.map((split) => (
              <Tabs.Trigger key={split} value={split}>
                {split}
                <Text as="span" color="fg.muted" ml={2} textStyle="readout" fontSize="xs">
                  {formatNumber(counts[split])}
                </Text>
              </Tabs.Trigger>
            ))}
          </Tabs.List>
          {SPLITS.map((split) => (
            <Tabs.Content key={split} value={split} pt={5}>
              <ImageGallery datasetId={datasetId} split={split} />
            </Tabs.Content>
          ))}
        </Tabs.Root>
      </SurfaceCard>

      <RoboflowUploadModal
        open={sending}
        onClose={() => setSending(false)}
        version={data.version}
        pending={send.isPending}
        onConfirm={(payload) => send.mutate(payload, { onSuccess: () => setSending(false) })}
      />

      <Modal
        open={deleting}
        onClose={() => {
          setDeleting(false);
          setTyped("");
        }}
        title={`Excluir ${data.version}?`}
        confirmLabel="Excluir para sempre"
        tone="danger"
        confirmDisabled={typed.trim() !== data.version}
        confirmLoading={remove.isPending}
        onConfirm={() =>
          remove.mutate(
            { id: datasetId, confirm: typed.trim() },
            { onSuccess: () => setDeleting(false) },
          )
        }
      >
        <Flex direction="column" gap={3}>
          <Text fontSize="sm">
            Apaga as {formatNumber(counts.total)} imagens, a pasta <code>raw/</code> e o manifesto.
            Não há como desfazer, e o voo não pode ser recoletado.
          </Text>
          <Text fontSize="sm" color="fg.muted">
            Para confirmar, digite <b>{data.version}</b>:
          </Text>
          <Input
            size="sm"
            value={typed}
            placeholder={data.version}
            onChange={(event) => setTyped(event.target.value)}
          />
        </Flex>
      </Modal>
    </Flex>
  );
}

function SplitWarningNotice({ warning }: { warning: SplitWarning }) {
  return (
    <Notice tone={warning.level === "error" ? "signal.down" : "signal.warn"}>
      {warning.message}
    </Notice>
  );
}

function Notice({ tone, children }: { tone: string; children: React.ReactNode }) {
  return (
    <Flex
      align="flex-start"
      gap={2}
      px={4}
      py={3}
      rounded="card"
      borderWidth="1px"
      borderColor={tone}
      bg="bg.subtle"
    >
      <Box color={tone} mt="2px" flexShrink={0}>
        <TriangleAlert size={16} />
      </Box>
      <Text fontSize="sm">{children}</Text>
    </Flex>
  );
}
