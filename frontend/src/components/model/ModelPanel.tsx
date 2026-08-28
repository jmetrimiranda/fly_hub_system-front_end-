import { Box, Button, Flex, Switch, Text } from "@chakra-ui/react";
import { RefreshCw } from "lucide-react";
import { SurfaceCard } from "@/components/ui/SurfaceCard";
import { StatusDot } from "@/components/ui/StatusDot";
import { useModel, useModelControls } from "@/hooks/useModel";
import { formatDateTime } from "@/lib/format";
import type { ModelState } from "@/types/api";

/**
 * Painel do modelo, ao lado do Pipeline na tela Voo.
 *
 * Duas ações e nenhuma delas envia arquivo. Quem treina copia `best.pt` para
 * `models/` e a aplicação percebe sozinha — se a tela precisasse de um botão
 * "carregar modelo", o contrato de cinco passos de `models/README.md` estaria
 * quebrado.
 *
 * **Desligar não descarrega os pesos.** É o que permite alternar durante um
 * voo para comparar com e sem detecção, sem pagar de novo os segundos de
 * carga. `Recarregar` é a outra ação: relê o disco, não mexe no toggle.
 */
export function ModelPanel() {
  const model = useModel();
  const controls = useModelControls();

  const state = model.data;
  const tone = badgeTone(state);

  return (
    <SurfaceCard title="Modelo" padding={5}>
      <Flex direction="column" gap={4}>
        <Flex align="center" gap={2}>
          <StatusDot tone={tone} />
          <Text textStyle="readout" fontSize="sm">
            {label(state)}
          </Text>
        </Flex>

        <Text fontSize="xs" color="fg.muted">
          {state?.message ?? "Consultando o estado do modelo…"}
        </Text>

        <Flex align="center" justify="space-between" gap={3}>
          <Switch.Root
            checked={state?.enabled ?? true}
            // Sem pesos não há o que ligar; o texto acima já diz o porquê.
            disabled={!state?.loaded || controls.toggle.isPending}
            onCheckedChange={(event) => controls.toggle.mutate(event.checked)}
            colorPalette="teal"
            size="sm"
          >
            <Switch.HiddenInput aria-label="Inferência sobre o vídeo" />
            <Switch.Control>
              <Switch.Thumb />
            </Switch.Control>
            <Switch.Label fontSize="sm">Inferência</Switch.Label>
          </Switch.Root>

          <Button
            size="xs"
            variant="outline"
            loading={controls.reload.isPending}
            onClick={() => controls.reload.mutate()}
          >
            <RefreshCw size={14} /> Recarregar
          </Button>
        </Flex>

        {state && <Details state={state} />}
      </Flex>
    </SurfaceCard>
  );
}

function badgeTone(state: ModelState | undefined): "live" | "warn" | "down" | "idle" {
  if (!state) return "idle";
  if (state.active) return "live";
  if (state.error) return "down";
  return "warn";
}

function label(state: ModelState | undefined): string {
  if (!state) return "…";
  if (state.active) return `ATIVO · ${state.weights_name}`;
  if (state.error) return "NÃO CARREGOU";
  if (state.loaded) return "DESLIGADO";
  return "SEM MODELO";
}

/** Métricas do treino. Ausentes, o modelo funciona igual — a tela só não as mostra. */
function Details({ state }: { state: ModelState }) {
  const metrics = state.metrics;

  return (
    <Flex direction="column" gap={2} pt={3} borderTopWidth="1px" borderColor="border.subtle">
      <Row label="Arquivo" value={state.weights_path} />
      {state.loaded_at && <Row label="Carregado" value={formatDateTime(state.loaded_at)} />}
      {state.classes.length > 0 && <Row label="Classes" value={state.classes.join(", ")} />}

      {metrics ? (
        <>
          {metrics.trained_at && <Row label="Treinado" value={formatDateTime(metrics.trained_at)} />}
          <Row label="mAP@50" value={percent(metrics.map50)} />
          <Row label="mAP@50-95" value={percent(metrics.map50_95)} />
          <Row label="Precisão" value={percent(metrics.precision)} />
          <Row label="Recall" value={percent(metrics.recall)} />
          {metrics.split_check_ok === false && (
            <Text fontSize="xs" color="signal.warn" mt={1}>
              O treino avisou que a partição do dataset baixado não bateu com o split temporal.
              Estas métricas provavelmente estão otimistas — quadros vizinhos no tempo caíram em
              partições diferentes.
            </Text>
          )}
        </>
      ) : (
        <Text fontSize="xs" color="fg.muted">
          {state.metrics_error
            ? `O metrics.json existe mas não pôde ser lido: ${state.metrics_error}`
            : "Sem metrics.json ao lado dos pesos — o modelo funciona igual, só não há mAP para mostrar."}
        </Text>
      )}
    </Flex>
  );
}

function Row({ label: name, value }: { label: string; value: string }) {
  return (
    <Flex justify="space-between" gap={3} align="baseline">
      <Text fontSize="xs" color="fg.muted" flexShrink={0}>
        {name}
      </Text>
      <Box textAlign="end" minW={0}>
        <Text textStyle="readout" fontSize="xs" truncate>
          {value}
        </Text>
      </Box>
    </Flex>
  );
}

/** Travessão, não zero: métrica ausente não é métrica igual a zero. */
function percent(value: number | null): string {
  return value === null ? "—" : `${(value * 100).toFixed(1)}%`;
}
