/**
 * Ponte entre o canal SSE do backend e o cache do TanStack Query.
 *
 * O backend é a única fonte de verdade. Quando ele muda de estado — conexão
 * caiu, coleta salva, pipeline parado — publica um evento e este hook
 * invalida exatamente a chave afetada. Sem polling agressivo e sem cópia do
 * estado do servidor em um store do cliente (ADR 001 e 002).
 */
import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { eventsUrl } from "@/services/api";
import { keys } from "@/lib/queryKeys";
import { emitTelemetry } from "@/hooks/useTelemetry";
import { useUiStore } from "@/stores/uiStore";
import type { Telemetry } from "@/types/api";

/**
 * `flight.telemetry` não está no mapa abaixo de propósito: é o único evento que
 * carrega o próprio dado em vez de avisar que algo mudou, e portanto o único
 * que não invalida chave nenhuma. O motivo — 1 Hz por cliente conectado — está
 * no ADR 006. Todo evento novo entra no mapa, não aqui.
 */
const INVALIDATION_MAP: Record<string, readonly (readonly unknown[])[]> = {
  "flight.connection": [keys.flight.all, keys.dashboard.summary()],
  "flight.endpoint": [keys.flight.status()],
  "collection.started": [keys.flight.collection(), keys.flight.preflight()],
  // A pausa automática — disco cheio ou limite de quadros — acontece sem
  // ninguém clicar em nada. Sem este evento a tela continuaria dizendo
  // "Gravando" com a gravação parada.
  "collection.paused": [keys.flight.collection()],
  "collection.resumed": [keys.flight.collection()],
  "collection.saved": [keys.flight.collection(), keys.flight.preflight(), keys.datasets.all],
  "collection.cancelled": [keys.flight.collection(), keys.flight.preflight()],
  "pipeline.status": [keys.flight.pipeline()],
  "roboflow.started": [keys.datasets.all],
  "roboflow.progress": [keys.datasets.all],
  "roboflow.finished": [keys.datasets.all],
};

export function useServerEvents() {
  const queryClient = useQueryClient();
  const setLive = useUiStore((state) => state.setEventsConnected);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const source = new EventSource(eventsUrl());
    sourceRef.current = source;

    source.onopen = () => setLive(true);
    source.onerror = () => setLive(false); // o navegador reconecta sozinho

    for (const [event, targets] of Object.entries(INVALIDATION_MAP)) {
      source.addEventListener(event, () => {
        targets.forEach((queryKey) => queryClient.invalidateQueries({ queryKey }));
      });
    }

    source.addEventListener("flight.telemetry", (event) => {
      emitTelemetry(JSON.parse((event as MessageEvent<string>).data) as Telemetry);
    });

    return () => {
      source.close();
      setLive(false);
    };
  }, [queryClient, setLive]);

  return sourceRef;
}
