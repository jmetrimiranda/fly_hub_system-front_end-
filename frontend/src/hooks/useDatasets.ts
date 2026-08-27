import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { datasetService } from "@/services/api";
import { keys } from "@/lib/queryKeys";

export function useDatasets(page = 1) {
  return useQuery({ queryKey: keys.datasets.list(page), queryFn: () => datasetService.list(page) });
}

export function useSendToRoboflow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (datasetId: number) => datasetService.sendToRoboflow(datasetId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.datasets.all }),
  });
}
