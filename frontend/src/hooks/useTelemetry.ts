/**
 * Posição e rastro da aeronave.
 *
 * A telemetria chega a 1 Hz e é o único evento SSE que carrega o próprio dado
 * (ADR 006). Ela **não** entra no cache do TanStack Query nem em um store do
 * Zustand: não é estado de servidor cacheável — escrever no cache a cada
 * segundo invalidaria dependentes sem parar — nem estado de aplicação, porque
 * ninguém além do mapa a consulta. Fica em `useState` local deste hook e morre
 * junto com o componente que a usa.
 *
 * O `EventSource` continua sendo um só, o de `useServerEvents()`. Ele encaminha
 * cada amostra para `emitTelemetry()`, e é daqui que os assinantes a recebem.
 */
import { useEffect, useState } from "react";
import { flightService } from "@/services/api";
import type { Telemetry } from "@/types/api";

/** 120 posições ≈ 2 minutos de voo a 1 Hz. */
export const TRAIL_LENGTH = 120;

export type TrailPoint = [latitude: number, longitude: number];

export interface TelemetryFeed {
  current: Telemetry | null;
  /** Amostra anterior — é entre ela e `current` que o mapa interpola. */
  previous: Telemetry | null;
  /** `performance.now()` de quando `current` chegou, âncora da interpolação. */
  receivedAt: number;
  trail: TrailPoint[];
}

type Listener = (sample: Telemetry) => void;

const listeners = new Set<Listener>();

/** Ponte vinda de `useServerEvents()`, o único dono do EventSource. */
export function emitTelemetry(sample: Telemetry): void {
  for (const listener of listeners) listener(sample);
}

const EMPTY: TelemetryFeed = { current: null, previous: null, receivedAt: 0, trail: [] };

function append(feed: TelemetryFeed, sample: Telemetry): TelemetryFeed {
  const trail = [...feed.trail, [sample.latitude, sample.longitude] as TrailPoint];
  return {
    current: sample,
    previous: feed.current,
    receivedAt: performance.now(),
    trail: trail.length > TRAIL_LENGTH ? trail.slice(-TRAIL_LENGTH) : trail,
  };
}

export function useTelemetry(): TelemetryFeed {
  const [feed, setFeed] = useState<TelemetryFeed>(EMPTY);

  useEffect(() => {
    const listener: Listener = (sample) => setFeed((previous) => append(previous, sample));
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, []);

  // Uma leitura só, na montagem: o mapa abre já posicionado em vez de esperar
  // o próximo tick. Depois disso quem manda é o evento.
  useEffect(() => {
    let active = true;
    flightService
      .getTelemetry()
      .then((sample) => {
        if (!active || !sample) return;
        setFeed((previous) => (previous.current ? previous : append(previous, sample)));
      })
      .catch(() => {
        // Sem posição inicial o mapa abre no centro da área de operação. Não é
        // erro de tela: a próxima amostra do SSE resolve.
      });
    return () => {
      active = false;
    };
  }, []);

  return feed;
}
