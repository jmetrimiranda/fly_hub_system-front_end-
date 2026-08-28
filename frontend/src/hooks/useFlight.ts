/**
 * Hooks do domínio Voo.
 *
 * Cada mutação invalida o que mudou e nada além disso. O componente não sabe
 * o que precisa ser recarregado — essa decisão mora aqui.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { flightService } from "@/services/api";
import { keys } from "@/lib/queryKeys";
import type { CollectionStartParams } from "@/types/api";

export function useFlightStatus() {
  return useQuery({
    queryKey: keys.flight.status(),
    queryFn: flightService.getStatus,
    // Rede de segurança caso o SSE caia; o intervalo é folgado de propósito.
    refetchInterval: 15_000,
  });
}

/**
 * A coleta em curso. Enquanto o gravador está no ar, os contadores mudam a
 * cada quadro salvo e nenhum evento SSE os acompanha — a gravação acontece em
 * thread, e publicar um evento por quadro inundaria o canal. Por isso, e só
 * enquanto há coleta ativa, isto revalida a cada segundo.
 */
export function useCurrentCollection() {
  return useQuery({
    queryKey: keys.flight.collection(),
    queryFn: flightService.getCurrentCollection,
    refetchInterval: (query) => (query.state.data?.progress ? 1000 : false),
  });
}

/**
 * A guarda da coleta. Revalida sozinha porque é ela que habilita o botão: o
 * stream cai enquanto ninguém olha, e um botão clicável que falha depois é
 * pior que um botão desabilitado que explica.
 */
export function useCollectionPreflight() {
  return useQuery({
    queryKey: keys.flight.preflight(),
    queryFn: flightService.getCollectionPreflight,
    refetchInterval: 10_000,
  });
}

export function usePipeline() {
  return useQuery({ queryKey: keys.flight.pipeline(), queryFn: flightService.getPipeline });
}

export function useCollectionControls() {
  const queryClient = useQueryClient();
  const invalidate = (keysToClear: readonly (readonly unknown[])[]) =>
    keysToClear.forEach((queryKey) => queryClient.invalidateQueries({ queryKey }));

  const start = useMutation({
    mutationFn: (params: CollectionStartParams) => flightService.startCollection(params),
    onSuccess: () => invalidate([keys.flight.collection(), keys.flight.preflight()]),
  });
  const pause = useMutation({
    mutationFn: flightService.pauseCollection,
    onSuccess: () => invalidate([keys.flight.collection()]),
  });
  const resume = useMutation({
    mutationFn: flightService.resumeCollection,
    onSuccess: () => invalidate([keys.flight.collection()]),
  });
  const save = useMutation({
    mutationFn: flightService.saveCollection,
    onSuccess: () =>
      invalidate([keys.flight.collection(), keys.flight.preflight(), keys.datasets.all]),
  });
  const cancel = useMutation({
    mutationFn: flightService.cancelCollection,
    onSuccess: () =>
      invalidate([keys.flight.collection(), keys.flight.preflight(), keys.datasets.all]),
  });

  return { start, pause, resume, save, cancel };
}

export function usePipelineControls() {
  const queryClient = useQueryClient();
  const onSuccess = () => queryClient.invalidateQueries({ queryKey: keys.flight.pipeline() });

  return {
    start: useMutation({ mutationFn: flightService.startPipeline, onSuccess }),
    stop: useMutation({ mutationFn: flightService.stopPipeline, onSuccess }),
  };
}

export function useEndpointUpdate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (endpoint: string) => flightService.setEndpoint(endpoint),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.flight.status() }),
  });
}
