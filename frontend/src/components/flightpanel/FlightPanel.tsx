/**
 * O painel de voo do Dashboard.
 *
 * Desconectado mostra o drone parado. Quando a conexão se estabelece e se
 * sustenta, as hélices aceleram, o drone decola e, alguns segundos depois, o
 * painel dá lugar ao mapa com a posição real da aeronave. A cerimônia existe
 * para tornar a transição legível — trocar de tela no instante do `connected`
 * pareceria falha de carregamento.
 *
 * Quem decide o quê e quando é `useFlightPanelState`; aqui só se renderiza.
 */
import { Suspense, lazy, useEffect, useState } from "react";
import { Box, Flex, IconButton, Spinner } from "@chakra-ui/react";
import { Box as CubeIcon, Map as MapIcon } from "lucide-react";
import { DroneViewer } from "@/components/drone3d/DroneViewer";
import { useFlightPanelState } from "./useFlightPanelState";

// O Leaflet inteiro entra por aqui, e só quando o mapa aparece pela primeira
// vez — no mínimo oito segundos depois de conectar.
const FlightMap = lazy(() => import("@/components/map/FlightMap"));

/** Sem deslocamento: conteúdo pulando em painel pequeno lê como erro. */
const FADE_MS = 240;

interface Props {
  connected: boolean;
  height?: string | number;
}

export function FlightPanel({ connected, height = "100%" }: Props) {
  const { isFlying, showMap, label, toggle } = useFlightPanelState(connected);

  // Uma vez carregado, o mapa fica montado: alternar de volta para o drone não
  // deve custar reconstruir o Leaflet e perder o rastro acumulado.
  const [mapLoaded, setMapLoaded] = useState(showMap);
  useEffect(() => {
    if (showMap) setMapLoaded(true);
  }, [showMap]);

  return (
    <Box position="relative" height={height} minH="260px">
      <Box
        position="absolute"
        inset={0}
        opacity={showMap ? 0 : 1}
        pointerEvents={showMap ? "none" : "auto"}
        transition={`opacity ${FADE_MS}ms ease`}
      >
        <DroneViewer isFlying={isFlying} label={label} />
      </Box>

      {mapLoaded && (
        <Box
          position="absolute"
          inset={0}
          opacity={showMap ? 1 : 0}
          pointerEvents={showMap ? "auto" : "none"}
          transition={`opacity ${FADE_MS}ms ease`}
        >
          <Suspense
            fallback={
              <Flex height="100%" align="center" justify="center" rounded="card" bg="bg.viewer">
                <Spinner size="sm" color="whiteAlpha.700" />
              </Flex>
            }
          >
            <FlightMap />
          </Suspense>
        </Box>
      )}

      {connected && (
        <IconButton
          aria-label={showMap ? "Ver o drone em 3D" : "Ver o mapa do voo"}
          title={showMap ? "Ver o drone em 3D" : "Ver o mapa do voo"}
          onClick={toggle}
          position="absolute"
          top={4}
          right={4}
          // Acima dos painéis do Leaflet, que chegam a z-index 800.
          zIndex={900}
          size="sm"
          variant="plain"
          color="white"
          bg="blackAlpha.600"
          backdropFilter="blur(8px)"
          rounded="control"
          _hover={{ bg: "blackAlpha.700" }}
        >
          {showMap ? <CubeIcon size={16} /> : <MapIcon size={16} />}
        </IconButton>
      )}
    </Box>
  );
}
