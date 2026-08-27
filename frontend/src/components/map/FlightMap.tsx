/**
 * O mapa da área de operação.
 *
 * Carregado por `import()` dinâmico a partir do `FlightPanel`: o Leaflet só é
 * baixado quando o painel troca para o mapa pela primeira vez, o que acontece
 * no mínimo oito segundos depois da conexão. É download de graça.
 *
 * Este componente não busca nada nem conhece rota da API: a posição vem de
 * `useTelemetry()`, alimentado pelo evento SSE.
 */
import "leaflet/dist/leaflet.css";

import { useEffect, useMemo, useRef } from "react";
import { Box, Flex, Text, useToken } from "@chakra-ui/react";
import { divIcon } from "leaflet";
import type { LatLngTuple, Marker as LeafletMarker } from "leaflet";
import { MapContainer, Marker, Polyline, TileLayer, useMap } from "react-leaflet";
import { usePrefersReducedMotion } from "@/components/drone3d/usePrefersReducedMotion";
import { useTelemetry } from "@/hooks/useTelemetry";
import type { Telemetry } from "@/types/api";

/** Terminal Marítimo de Ponta Ubu, Anchieta/ES. */
export const MAP_CENTER: LatLngTuple = [-20.78667, -40.57333];
export const MAP_ZOOM = 16;

// Mapa de ruas do OpenStreetMap. Num terminal portuário a imagem de satélite é
// bem mais legível — a troca é substituir estas duas constantes por um provedor
// de imagery, mantendo a atribuição do provedor visível como manda a licença.
const TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';

/** Intervalo esperado entre amostras — é ao longo dele que o marcador anda. */
const SAMPLE_INTERVAL_MS = 1000;

/**
 * Fração central da viewport em que o drone pode circular sem recentrar.
 * Recentrar a cada amostra tira o mapa da mão de quem está arrastando.
 */
const SAFE_AREA = 0.6;

function arrowIcon(color: string, headingDeg: number) {
  // `divIcon` e não imagem: a seta precisa girar e sair na cor do tema.
  return divIcon({
    className: "flight-marker",
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    html: `<svg viewBox="0 0 24 24" width="28" height="28" aria-hidden="true"
      style="display:block;transform:rotate(${headingDeg}deg);filter:drop-shadow(0 1px 3px rgba(0,0,0,0.55))">
      <path d="M12 2 L19 21 L12 17 L5 21 Z" fill="${color}"
        stroke="white" stroke-width="1.2" stroke-linejoin="round" />
    </svg>`,
  });
}

interface MarkerProps {
  current: Telemetry;
  previous: Telemetry | null;
  receivedAt: number;
  color: string;
  reduced: boolean;
}

/**
 * A 1 Hz o marcador andaria aos saltos, e salto de segundo em segundo lê como
 * travamento, não como voo. Aqui ele percorre o trecho entre a amostra anterior
 * e a atual ao longo do intervalo esperado, quadro a quadro.
 *
 * A animação roda direto no objeto do Leaflet, fora do React: reposicionar por
 * estado seria re-renderizar a árvore a 60 Hz para mover um ícone.
 */
function DroneMarker({ current, previous, receivedAt, color, reduced }: MarkerProps) {
  const markerRef = useRef<LeafletMarker | null>(null);
  const heading = Math.round(current.heading_deg);
  const icon = useMemo(() => arrowIcon(color, heading), [color, heading]);

  const target: LatLngTuple = [current.latitude, current.longitude];
  const animated = !reduced && previous !== null;
  // O React ancora o marcador onde a animação começa; daí em diante quem manda
  // é o `requestAnimationFrame`. Assim os dois não disputam a mesma posição.
  const anchor: LatLngTuple =
    animated && previous ? [previous.latitude, previous.longitude] : target;

  const [targetLat, targetLon] = target;
  const [fromLat, fromLon] = anchor;

  useEffect(() => {
    const marker = markerRef.current;
    if (!marker) return;

    if (!animated) {
      marker.setLatLng([targetLat, targetLon]);
      return;
    }

    let frame = 0;
    const step = () => {
      const ratio = Math.min(1, (performance.now() - receivedAt) / SAMPLE_INTERVAL_MS);
      marker.setLatLng([
        fromLat + (targetLat - fromLat) * ratio,
        fromLon + (targetLon - fromLon) * ratio,
      ]);
      if (ratio < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [animated, fromLat, fromLon, targetLat, targetLon, receivedAt]);

  return <Marker ref={markerRef} position={anchor} icon={icon} />;
}

/** Recentra só quando o drone sai da área segura — ver `SAFE_AREA`. */
function KeepInView({ latitude, longitude }: { latitude: number; longitude: number }) {
  const map = useMap();

  useEffect(() => {
    const size = map.getSize();
    const point = map.latLngToContainerPoint([latitude, longitude]);
    const marginX = (size.x * (1 - SAFE_AREA)) / 2;
    const marginY = (size.y * (1 - SAFE_AREA)) / 2;
    const outside =
      point.x < marginX ||
      point.x > size.x - marginX ||
      point.y < marginY ||
      point.y > size.y - marginY;

    if (outside) map.panTo([latitude, longitude]);
  }, [map, latitude, longitude]);

  return null;
}

function Readout({ sample }: { sample: Telemetry }) {
  return (
    <Flex
      position="absolute"
      left={4}
      bottom={4}
      zIndex={500}
      direction="column"
      gap={0.5}
      bg="blackAlpha.600"
      backdropFilter="blur(8px)"
      px={3}
      py={2}
      rounded="control"
      color="white"
    >
      <Text textStyle="readout" fontSize="xs">
        {sample.latitude.toFixed(6)}, {sample.longitude.toFixed(6)}
      </Text>
      <Text textStyle="readout" fontSize="xs" color="whiteAlpha.800">
        {sample.altitude_m.toFixed(1)} m · {Math.round(sample.heading_deg)}° ·{" "}
        {sample.fix_type.toUpperCase()}
      </Text>
    </Flex>
  );
}

export default function FlightMap() {
  const { current, previous, receivedAt, trail } = useTelemetry();
  const reduced = usePrefersReducedMotion();
  const [markerColor] = useToken("colors", "signal.live");

  // Só na montagem: depois disso quem move o mapa é o `KeepInView` ou o operador.
  const initialCenter: LatLngTuple = current
    ? [current.latitude, current.longitude]
    : MAP_CENTER;

  return (
    <Box
      position="relative"
      height="100%"
      minH="260px"
      rounded="card"
      overflow="hidden"
      borderWidth="1px"
      borderColor="border.subtle"
      css={{
        ".leaflet-container": { height: "100%", width: "100%", background: "#0B1120" },
        // A atribuição é obrigatória pela licença do OSM: fica legível, não escondida.
        ".leaflet-control-attribution": { fontSize: "10px" },
      }}
    >
      <MapContainer center={initialCenter} zoom={MAP_ZOOM} scrollWheelZoom>
        <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION} />
        {trail.length > 1 && (
          <Polyline
            positions={trail}
            pathOptions={{ color: markerColor, weight: 3, opacity: 0.7 }}
          />
        )}
        {current && (
          <>
            <DroneMarker
              current={current}
              previous={previous}
              receivedAt={receivedAt}
              color={markerColor}
              reduced={reduced}
            />
            <KeepInView latitude={current.latitude} longitude={current.longitude} />
          </>
        )}
      </MapContainer>

      {current && <Readout sample={current} />}
    </Box>
  );
}
