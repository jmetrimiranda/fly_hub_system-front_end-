import { useEffect, useState } from "react";
import { Box, Button, Flex, Grid, GridItem, Input, Table, Text } from "@chakra-ui/react";
import { Camera, Copy, Pause, Play, Save, Square, TriangleAlert } from "lucide-react";
import { InferenceStream } from "@/components/video/InferenceStream";
import { StatCard } from "@/components/ui/StatCard";
import { SurfaceCard } from "@/components/ui/SurfaceCard";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { StatusDot } from "@/components/ui/StatusDot";
import {
  useCollectionControls,
  useCurrentCollection,
  useEndpointUpdate,
  useFlightStatus,
  usePipeline,
  usePipelineControls,
} from "@/hooks/useFlight";
import { formatDateTime, formatDuration, formatNumber } from "@/lib/format";

export function FlightPage() {
  const status = useFlightStatus();
  const collection = useCurrentCollection();
  const pipeline = usePipeline();
  const controls = useCollectionControls();
  const pipelineControls = usePipelineControls();
  const endpointUpdate = useEndpointUpdate();

  const [endpoint, setEndpoint] = useState("");
  useEffect(() => {
    if (status.data?.endpoint) setEndpoint(status.data.endpoint);
  }, [status.data?.endpoint]);

  if (status.isLoading) return <LoadingState label="Consultando o FlightHub…" />;
  if (status.isError) return <ErrorState error={status.error} onRetry={() => status.refetch()} />;

  const indicators = status.data!.indicators;
  const metrics = status.data!.metrics;
  const active = collection.data;
  const running = pipeline.data?.status === "running";

  return (
    <>
      <Grid templateColumns={{ base: "1fr", sm: "1fr 1fr", xl: "repeat(4, 1fr)" }} gap={4} mb={6}>
        <StatCard
          label="Disponibilidade"
          value={indicators.availability_label}
          status={indicators.availability ? "live" : "down"}
        />
        <StatCard
          label="MediaMTX"
          value={indicators.mediamtx_label}
          status={indicators.mediamtx_up ? "live" : "down"}
        />
        <StatCard
          label="Túnel"
          value={indicators.tunnel_label}
          status={indicators.tunnel_up ? "live" : "idle"}
        />
        <StatCard
          label="Stream"
          value={indicators.stream_label}
          status={indicators.stream_up ? "live" : "idle"}
        />
      </Grid>

      <Grid templateColumns={{ base: "1fr", xl: "minmax(0, 2fr) minmax(320px, 1fr)" }} gap={6}>
        {/* Vídeo com o resultado do modelo aplicado — fluxo separado do Dataset */}
        <GridItem>
          {metrics.resolution_change && (
            <Flex
              align="flex-start"
              gap={2}
              mb={3}
              px={4}
              py={3}
              rounded="card"
              borderWidth="1px"
              borderColor="signal.warn"
              bg="bg.subtle"
            >
              <Box color="signal.warn" mt="2px">
                <TriangleAlert size={16} />
              </Box>
              <Text fontSize="sm">
                A resolução do stream mudou de {metrics.resolution_change.previous} para{" "}
                {metrics.resolution_change.current} às{" "}
                {formatDateTime(metrics.resolution_change.at)}. Costuma ser a qualidade do canal em
                “Automático” no FlightHub, e é a causa mais comum de queda da captura — uma coleta
                feita agora sai com resoluções misturadas.
              </Text>
            </Flex>
          )}
          <InferenceStream connected={status.data!.connected} metrics={metrics} />
        </GridItem>

        {/* Trilho de controles */}
        <GridItem>
          <Flex direction="column" gap={4}>
            <SurfaceCard title="Coleta de imagens" padding={5}>
              {!active && (
                <>
                  <Button
                    width="100%"
                    colorPalette="teal"
                    loading={controls.start.isPending}
                    onClick={() => controls.start.mutate()}
                  >
                    <Camera size={16} /> Coletar imagens do voo
                  </Button>
                  <Text fontSize="xs" color="fg.muted" mt={3}>
                    A coleta grava os frames originais e particiona ao salvar.
                  </Text>
                </>
              )}

              {active && (
                <>
                  <Flex align="center" gap={2} mb={3}>
                    <StatusDot tone={active.status === "recording" ? "live" : "warn"} />
                    <Text textStyle="readout" fontSize="sm">
                      {active.version} · {formatNumber(active.image_count)} imagens
                    </Text>
                  </Flex>
                  <Flex gap={2}>
                    {active.status === "recording" ? (
                      <Button
                        flex="1"
                        variant="outline"
                        loading={controls.pause.isPending}
                        onClick={() => controls.pause.mutate()}
                      >
                        <Pause size={16} /> Pausar
                      </Button>
                    ) : (
                      <Button
                        flex="1"
                        variant="outline"
                        loading={controls.resume.isPending}
                        onClick={() => controls.resume.mutate()}
                      >
                        <Play size={16} /> Continuar
                      </Button>
                    )}
                    <Button
                      flex="1"
                      colorPalette="teal"
                      loading={controls.save.isPending}
                      onClick={() => controls.save.mutate()}
                    >
                      <Save size={16} /> Salvar
                    </Button>
                  </Flex>
                </>
              )}
            </SurfaceCard>

            <SurfaceCard title="Pipeline" padding={5}>
              <Flex align="center" gap={2} mb={3}>
                <StatusDot tone={running ? "live" : "idle"} />
                <Text textStyle="readout" fontSize="sm">
                  {running ? "EXECUTANDO" : "PARADO"}
                </Text>
              </Flex>
              <Flex gap={2}>
                <Button
                  flex="1"
                  colorPalette="teal"
                  disabled={running}
                  loading={pipelineControls.start.isPending}
                  onClick={() => pipelineControls.start.mutate()}
                >
                  <Play size={16} /> Iniciar
                </Button>
                <Button
                  flex="1"
                  variant="outline"
                  colorPalette="red"
                  disabled={!running}
                  loading={pipelineControls.stop.isPending}
                  onClick={() => pipelineControls.stop.mutate()}
                >
                  <Square size={16} /> Parar
                </Button>
              </Flex>
              {pipeline.data?.message && (
                <Text fontSize="xs" color="fg.muted" mt={3}>
                  {pipeline.data.message}
                </Text>
              )}
            </SurfaceCard>

            <SurfaceCard title="Endereço para o FlightHub" padding={5}>
              <Flex gap={2} mb={3}>
                <Input
                  value={endpoint}
                  onChange={(event) => setEndpoint(event.target.value)}
                  fontFamily="mono"
                  fontSize="sm"
                  placeholder="rtmp://host:porta/live/stream"
                />
                <Button
                  variant="subtle"
                  onClick={() => navigator.clipboard.writeText(status.data!.publish_url)}
                  aria-label="Copiar endereço de publicação"
                >
                  <Copy size={16} />
                </Button>
              </Flex>
              <Button
                width="100%"
                size="sm"
                variant="outline"
                loading={endpointUpdate.isPending}
                onClick={() => endpointUpdate.mutate(endpoint)}
              >
                Salvar endereço
              </Button>
              <Text fontSize="xs" color="fg.muted" mt={3}>
                O endereço é fixo: com o host público definido, ele não muda entre reinícios. Depois
                de colar no FlightHub, reedite o canal de encaminhamento e desligue e religue o
                toggle — sem isso o drone continua publicando no endereço antigo.
              </Text>
            </SurfaceCard>
          </Flex>
        </GridItem>

        <GridItem colSpan={{ base: 1, xl: 2 }}>
          <SurfaceCard title="Conexão">
            <Table.Root size="sm" variant="line">
              <Table.Header>
                <Table.Row>
                  <Table.ColumnHeader>Resolução</Table.ColumnHeader>
                  <Table.ColumnHeader>Taxa</Table.ColumnHeader>
                  <Table.ColumnHeader>FPS captura</Table.ColumnHeader>
                  <Table.ColumnHeader>FPS inferência</Table.ColumnHeader>
                  <Table.ColumnHeader>Latência</Table.ColumnHeader>
                  <Table.ColumnHeader>Quadros perdidos</Table.ColumnHeader>
                  <Table.ColumnHeader>Tempo de stream</Table.ColumnHeader>
                  <Table.ColumnHeader>Última atualização</Table.ColumnHeader>
                </Table.Row>
              </Table.Header>
              <Table.Body>
                <Table.Row>
                  <Table.Cell>{metrics.resolution ?? "—"}</Table.Cell>
                  <Table.Cell>{metrics.bitrate_mbps ? `${metrics.bitrate_mbps} Mbps` : "—"}</Table.Cell>
                  <Table.Cell>{metrics.capture_fps?.toFixed(1) ?? "—"}</Table.Cell>
                  <Table.Cell>{metrics.inference_fps?.toFixed(1) ?? "—"}</Table.Cell>
                  <Table.Cell>{metrics.latency_ms ? `${metrics.latency_ms} ms` : "—"}</Table.Cell>
                  <Table.Cell>{formatNumber(metrics.dropped_frames)}</Table.Cell>
                  <Table.Cell>{formatDuration(metrics.stream_uptime_seconds)}</Table.Cell>
                  <Table.Cell>
                    {status.data!.last_seen_at ? formatDateTime(status.data!.last_seen_at) : "—"}
                  </Table.Cell>
                </Table.Row>
              </Table.Body>
            </Table.Root>
          </SurfaceCard>
        </GridItem>
      </Grid>
    </>
  );
}
