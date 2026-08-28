/**
 * Hooks dos dados de demonstração.
 *
 * A remoção derruba `datasets`, `inspections` e `dashboard` de uma vez — é o
 * raro caso em que uma mutação atravessa domínios, porque o seed também
 * atravessa. Invalidar menos que isso deixaria a tela mostrando 45 inspeções
 * que já não existem.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { adminService } from "@/services/api";
import { keys } from "@/lib/queryKeys";

export function useDemoData() {
  return useQuery({ queryKey: keys.admin.demo(), queryFn: adminService.demoSummary });
}

export function useClearDemoData() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: adminService.clearDemo,
    onSuccess: () => {
      for (const queryKey of [
        keys.admin.all,
        keys.datasets.all,
        keys.inspections.all,
        keys.dashboard.all,
      ]) {
        queryClient.invalidateQueries({ queryKey });
      }
    },
  });
}
