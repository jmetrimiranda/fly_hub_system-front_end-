/**
 * Player do vídeo com inferência.
 *
 * MJPEG dispensa hls.js e video.js: um `<img>` apontando para o endpoint basta,
 * e o navegador troca o quadro sozinho enquanto a resposta multipart estiver
 * aberta. Fechar a aba encerra a resposta, e o backend libera o RTSP.
 *
 * O que o quadro mostra é a imagem **processada** — o resultado do modelo, com
 * a sobreposição desenhada pelo backend. A imagem original é assunto da tela
 * Dataset, e as duas nunca se misturam.
 */
import { useEffect, useState } from "react";
import { Box, Button, Flex, Text } from "@chakra-ui/react";
import { AlertTriangle, RotateCw } from "lucide-react";
import { StatusDot } from "@/components/ui/StatusDot";
import { flightService } from "@/services/api";
import type { ConnectionMetrics } from "@/types/api";

interface Props {
  /** Só monta o `<img>` com sinal: desconectado mantém o placeholder. */
  connected: boolean;
  metrics: ConnectionMetrics;
}

type Phase = "loading" | "playing" | "error";

/**
 * O badge nunca fica em silêncio, e é por isso que ele tem quatro rótulos.
 *
 * Os três primeiros são causas diferentes para a **mesma imagem**: vídeo cru,
 * sem caixa nenhuma. Sem pesos, com pesos que não carregaram, e com pesos
 * carregados e a inferência desligada de propósito. Quem olha a tela precisa
 * saber em qual dos três está — ver vídeo cru achando que o modelo não achou
 * nada é pior que não ver vídeo.
 */
function modelBadge(metrics: ConnectionMetrics): { tone: "live" | "warn" | "down"; label: string } {
  if (metrics.model_loaded && metrics.model_enabled) {
    return { tone: "live", label: `MODELO ${metrics.model_version ?? "ativo"}` };
  }
  if (metrics.model_loaded) {
    return { tone: "warn", label: "MODELO DESLIGADO — vídeo cru" };
  }
  if (metrics.model_error) {
    return { tone: "down", label: "MODELO NÃO CARREGOU — vídeo cru" };
  }
  return { tone: "warn", label: "SEM MODELO — vídeo cru" };
}

export function InferenceStream({ connected, metrics }: Props) {
  const [attempt, setAttempt] = useState(0);
  const [phase, setPhase] = useState<Phase>("loading");

  // Reconectar depois de uma queda: o estado volta a "carregando" tanto quando
  // o operador insiste quanto quando o sinal volta sozinho.
  useEffect(() => {
    setPhase("loading");
  }, [attempt, connected]);

  const badge = modelBadge(metrics);

  return (
    <Box
      rounded="card"
      overflow="hidden"
      bg="bg.viewer"
      borderWidth="1px"
      borderColor="border.subtle"
      minH="460px"
      position="relative"
    >
      {connected && phase !== "error" && (
        <img
          key={attempt}
          src={flightService.streamUrl(attempt)}
          alt="Vídeo do voo com as detecções do modelo"
          onLoad={() => setPhase("playing")}
          onError={() => setPhase("error")}
          style={{ width: "100%", height: "100%", objectFit: "contain", display: "block" }}
        />
      )}

      {(!connected || phase !== "playing") && (
        <Flex
          position="absolute"
          inset={0}
          align="center"
          justify="center"
          direction="column"
          gap={2}
          textAlign="center"
          px={6}
        >
          {!connected && (
            <>
              <Text textStyle="label" color="whiteAlpha.700">
                Stream com inferência
              </Text>
              <Text fontSize="sm" color="whiteAlpha.600" maxW="46ch">
                Sem sinal. Publique o endereço abaixo no FlightHub para começar.
              </Text>
            </>
          )}

          {connected && phase === "loading" && (
            <Text fontSize="sm" color="whiteAlpha.600">
              Conectando ao stream…
            </Text>
          )}

          {connected && phase === "error" && (
            <>
              <Box color="signal.down">
                <AlertTriangle size={20} />
              </Box>
              <Text fontSize="sm" color="whiteAlpha.800" maxW="46ch">
                {metrics.stream_error
                  ? `O vídeo foi interrompido: ${metrics.stream_error}.`
                  : "O vídeo foi interrompido."}{" "}
                O restante da tela continua funcionando.
              </Text>
              <Button size="sm" variant="outline" mt={2} onClick={() => setAttempt((n) => n + 1)}>
                <RotateCw size={14} /> Tentar novamente
              </Button>
            </>
          )}
        </Flex>
      )}

      <Flex
        position="absolute"
        left={4}
        bottom={4}
        align="center"
        gap={2}
        bg="blackAlpha.600"
        px={3}
        py={1.5}
        rounded="control"
      >
        <StatusDot tone={badge.tone} />
        <Text textStyle="readout" fontSize="xs" color="white">
          {badge.label}
        </Text>
      </Flex>
    </Box>
  );
}
