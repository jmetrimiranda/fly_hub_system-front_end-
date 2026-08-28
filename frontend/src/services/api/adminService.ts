import { api } from "./client";
import type { DemoDataSummary } from "@/types/api";

/**
 * Manutenção da instalação — hoje, só os dados de demonstração.
 *
 * Separado dos services de domínio porque apagar o seed toca datasets,
 * inspeções, notas e métricas ao mesmo tempo: pendurar isso em `datasetService`
 * faria um domínio mexer nos outros três.
 */
export const adminService = {
  /** Quanto de demonstração ainda existe. O modal mostra antes de apagar. */
  demoSummary: () => api.get<DemoDataSummary>("/admin/seed").then((r) => r.data),

  /** Remove **apenas** o que tem `source="seed"`. Coleta real não é tocada. */
  clearDemo: () => api.delete<DemoDataSummary>("/admin/seed").then((r) => r.data),
};
