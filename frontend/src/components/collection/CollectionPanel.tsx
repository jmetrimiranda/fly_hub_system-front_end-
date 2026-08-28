import { useState } from "react";
import { Box, Button, Flex, Text } from "@chakra-ui/react";
import { Camera, Pause, Play, Save, TriangleAlert, X } from "lucide-react";
import { SurfaceCard } from "@/components/ui/SurfaceCard";
import { StatusDot } from "@/components/ui/StatusDot";
import { Modal } from "@/components/ui/Modal";
import { PreflightModal } from "./PreflightModal";
import { StartCollectionModal } from "./StartCollectionModal";
import {
  useCollectionControls,
  useCollectionPreflight,
  useCurrentCollection,
} from "@/hooks/useFlight";
import { formatBytes, formatDuration, formatNumber } from "@/lib/format";
import type { CollectionSession } from "@/types/api";

/**
 * Trilho de controles da coleta.
 *
 * A guarda vem do servidor e o botão só habilita com ela verde. Clicar com
 * algo vermelho abre o modal que lista o que falta — não existe caminho em que
 * o botão esteja clicável e a chamada falhe depois.
 */
export function CollectionPanel() {
  const preflight = useCollectionPreflight();
  const collection = useCurrentCollection();
  const controls = useCollectionControls();

  const [blocked, setBlocked] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  const active = collection.data;
  // Enquanto a guarda não respondeu não se sabe nada: dizer "indicadores em
  // vermelho" nesse intervalo seria inventar um diagnóstico, e o modal abriria
  // sem nenhuma condição para listar.
  const checking = preflight.data === undefined;
  const ready = preflight.data?.ok ?? false;

  return (
    <SurfaceCard title="Coleta de imagens" padding={5}>
      {!active && (
        <>
          <Button
            width="100%"
            colorPalette="teal"
            loading={controls.start.isPending || checking}
            onClick={() => (ready ? setConfirming(true) : setBlocked(true))}
            // Nunca `disabled` com a guarda vermelha: um botão apagado não diz
            // por quê. Clicável, ele abre o modal que lista o que falta.
            opacity={ready || checking ? 1 : 0.55}
          >
            <Camera size={16} /> Coletar imagens do voo
          </Button>
          <Text fontSize="xs" color="fg.muted" mt={3}>
            {checking
              ? "Verificando as condições da coleta…"
              : ready
                ? `Grava os quadros originais em ${preflight.data?.next_version} e particiona ao salvar.`
                : "Indicadores em vermelho — clique para ver o que falta."}
          </Text>

          <PreflightModal
            open={blocked}
            onClose={() => setBlocked(false)}
            preflight={preflight.data}
          />
          {preflight.data && (
            <StartCollectionModal
              open={confirming}
              onClose={() => setConfirming(false)}
              preflight={preflight.data}
              pending={controls.start.isPending}
              onConfirm={(params) =>
                controls.start.mutate(params, { onSuccess: () => setConfirming(false) })
              }
            />
          )}
        </>
      )}

      {active && (
        <>
          <RecordingState session={active} />

          <Flex gap={2} mt={4}>
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

          <Button
            width="100%"
            size="xs"
            variant="ghost"
            colorPalette="red"
            mt={2}
            onClick={() => setCancelling(true)}
          >
            <X size={14} /> Descartar coleta
          </Button>

          <Modal
            open={cancelling}
            onClose={() => setCancelling(false)}
            title={`Descartar a coleta ${active.version}?`}
            confirmLabel="Descartar"
            tone="danger"
            confirmLoading={controls.cancel.isPending}
            onConfirm={() =>
              controls.cancel.mutate(undefined, { onSuccess: () => setCancelling(false) })
            }
          >
            <Text fontSize="sm">
              A gravação para e a coleta <b>não</b> é particionada — ela não vira uma versão
              utilizável. Os {formatNumber(active.image_count)} quadros já gravados continuam em
              disco: para aproveitá-los depois, use <b>Refazer split</b> na página Datasets.
            </Text>
          </Modal>
        </>
      )}
    </SurfaceCard>
  );
}

/**
 * O estado da gravação, sem ambiguidade.
 *
 * Quadros salvos, tempo, disco e o que foi descartado. Sem a linha de
 * descartes, o operador conta 500 amostras, encontra 180 arquivos e passa a
 * tarde procurando o erro que não existe.
 */
function RecordingState({ session }: { session: CollectionSession }) {
  const progress = session.progress;
  const recording = session.status === "recording";

  return (
    <>
      <Flex align="center" gap={2} mb={3}>
        <StatusDot tone={recording ? "live" : "warn"} />
        <Text textStyle="readout" fontSize="sm" fontWeight="700">
          {recording ? "GRAVANDO" : "PAUSADO"}
        </Text>
        <Text textStyle="readout" fontSize="sm" color="fg.muted">
          · {session.version}
        </Text>
      </Flex>

      {progress?.paused_reason && (
        <Warning>
          {progress.paused_reason}
        </Warning>
      )}
      {progress?.error && <Warning>{progress.error}</Warning>}
      {progress?.disk_over_limit && (
        <Warning>
          Disco em {progress.disk_percent.toFixed(0)}%. Libere espaço antes de continuar.
        </Warning>
      )}

      <Flex direction="column" gap={1.5}>
        <Row label="Quadros salvos" value={formatNumber(session.image_count)} />
        <Row label="Tempo decorrido" value={formatDuration(session.duration_seconds)} />
        <Row label="Em disco" value={formatBytes(session.disk_bytes)} />
        {progress && (
          <>
            <Row
              label="Descartados (repetidos)"
              value={formatNumber(progress.dedup_skipped)}
              muted
            />
            {progress.io_dropped > 0 && (
              <Row
                label="Descartados (escrita lenta)"
                value={formatNumber(progress.io_dropped)}
                muted
              />
            )}
            <Row
              label="Espaço livre"
              value={`${formatBytes(progress.disk_free_bytes)} · ${progress.disk_percent.toFixed(0)}% usado`}
              muted
            />
          </>
        )}
      </Flex>
    </>
  );
}

function Row({ label, value, muted = false }: { label: string; value: string; muted?: boolean }) {
  return (
    <Flex justify="space-between" gap={3}>
      <Text fontSize="xs" color="fg.muted">
        {label}
      </Text>
      <Text textStyle="readout" fontSize="xs" fontWeight={muted ? "400" : "700"} color={muted ? "fg.muted" : undefined}>
        {value}
      </Text>
    </Flex>
  );
}

function Warning({ children }: { children: React.ReactNode }) {
  return (
    <Flex
      align="flex-start"
      gap={2}
      mb={3}
      px={3}
      py={2}
      rounded="card"
      borderWidth="1px"
      borderColor="signal.warn"
      bg="bg.subtle"
    >
      <Box color="signal.warn" mt="2px">
        <TriangleAlert size={14} />
      </Box>
      <Text fontSize="xs">{children}</Text>
    </Flex>
  );
}
