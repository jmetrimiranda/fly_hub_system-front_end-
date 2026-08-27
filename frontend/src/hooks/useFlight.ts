/**
 * Hooks do domínio Voo.
 *
 * Cada mutação invalida o que mudou e nada além disso. O componente não sabe
 * o que precisa ser recarregado — essa decisão mora aqui.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { flightService } from "@/services/api";
import { keys } from "@/lib/queryKeys";

export function useFlightStatus() {
  return useQuery({
    queryKey: keys.flight.status(),
    queryFn: flightService.getStatus,
    // Rede de segurança caso o SSE caia; o intervalo é folgado de propósito.
    refetchInterval: 15_000,
  });
}

export function useCurrentCollection() {
  return useQuery({
    queryKey: keys.flight.collection(),
    queryFn: flightService.getCurrentCollection,
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
    mutationFn: flightService.startCollection,
    onSuccess: () => invalidate([keys.flight.collection()]),
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
    onSuccess: () => invalidate([keys.flight.collection(), keys.datasets.all]),
  });

  return { start, pause, resume, save };
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
