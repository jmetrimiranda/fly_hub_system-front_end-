/**
 * Hooks do domínio Dataset.
 *
 * Cada mutação invalida o que mudou e nada além disso. Excluir imagem derruba
 * `detail(id)` inteiro — que, pela hierarquia de `queryKeys`, leva a galeria
 * junto: as contagens mudaram e a grade não pode continuar exibindo o que
 * acabou de sair do disco.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { datasetService, roboflowService } from "@/services/api";
import { keys } from "@/lib/queryKeys";
import type {
  RoboflowCredentialInput,
  RoboflowUploadInput,
  SplitName,
} from "@/types/api";

export function useDatasets(page = 1) {
  return useQuery({ queryKey: keys.datasets.list(page), queryFn: () => datasetService.list(page) });
}

export function useDataset(id: number) {
  return useQuery({ queryKey: keys.datasets.detail(id), queryFn: () => datasetService.get(id) });
}

export function useDatasetImages(id: number, split: SplitName, page = 1) {
  return useQuery({
    queryKey: keys.datasets.images(id, split, page),
    queryFn: () => datasetService.images(id, split, page),
    // A grade pisca a cada troca de aba sem isto: o TanStack Query descarta os
    // dados anteriores enquanto busca os novos, e a página salta de altura.
    placeholderData: (previous) => previous,
  });
}

function useDatasetInvalidation(id: number) {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: keys.datasets.detail(id) });
    queryClient.invalidateQueries({ queryKey: keys.datasets.all });
  };
}

export function useDeleteImages(id: number) {
  const invalidate = useDatasetInvalidation(id);
  return useMutation({
    mutationFn: (imageIds: number[]) => datasetService.deleteImages(id, imageIds),
    onSuccess: invalidate,
  });
}

export function useResplit(id: number) {
  const invalidate = useDatasetInvalidation(id);
  return useMutation({ mutationFn: () => datasetService.resplit(id), onSuccess: invalidate });
}

export function useDeleteDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, confirm }: { id: number; confirm: string }) =>
      datasetService.remove(id, confirm),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.datasets.all }),
  });
}

/* --- Roboflow ------------------------------------------------------------- */

export function useRoboflowCredentials() {
  return useQuery({
    queryKey: keys.datasets.credentials(),
    queryFn: roboflowService.listCredentials,
  });
}

export function useSaveCredential() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: RoboflowCredentialInput) => roboflowService.createCredential(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.datasets.credentials() }),
  });
}

export function useDeleteCredential() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => roboflowService.deleteCredential(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.datasets.credentials() }),
  });
}

/**
 * Progresso do envio. Só consulta enquanto há envio ativo — um `refetchInterval`
 * fixo bateria no servidor para sempre depois que o lote terminou.
 */
export function useRoboflowUpload(id: number, enabled: boolean) {
  return useQuery({
    queryKey: keys.datasets.roboflow(id),
    queryFn: () => datasetService.roboflowStatus(id),
    enabled,
    refetchInterval: (query) => (query.state.data?.active ? 1500 : false),
  });
}

export function useSendToRoboflow(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: RoboflowUploadInput) => datasetService.sendToRoboflow(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.datasets.roboflow(id) });
      queryClient.invalidateQueries({ queryKey: keys.datasets.all });
    },
  });
}

export function useCancelRoboflow(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => datasetService.cancelRoboflow(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.datasets.roboflow(id) }),
  });
}
