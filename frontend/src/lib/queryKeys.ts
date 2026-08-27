/**
 * Chaves de cache em um lugar só.
 *
 * Invalidação errada é a falha mais comum com TanStack Query, e ela acontece
 * quando cada arquivo inventa a própria string. Aqui a hierarquia é explícita:
 * invalidar `keys.flight.all` derruba status, coleta e pipeline juntos.
 */
export const keys = {
  dashboard: {
    all: ["dashboard"] as const,
    summary: () => [...keys.dashboard.all, "summary"] as const,
    damageSeries: () => [...keys.dashboard.all, "damage-series"] as const,
    inspections: () => [...keys.dashboard.all, "inspections"] as const,
  },
  flight: {
    all: ["flight"] as const,
    status: () => [...keys.flight.all, "status"] as const,
    collection: () => [...keys.flight.all, "collection"] as const,
    pipeline: () => [...keys.flight.all, "pipeline"] as const,
  },
  datasets: {
    all: ["datasets"] as const,
    list: (page: number) => [...keys.datasets.all, "list", page] as const,
    detail: (id: number) => [...keys.datasets.all, "detail", id] as const,
  },
  inspections: {
    all: ["inspections"] as const,
    list: (page: number) => [...keys.inspections.all, "list", page] as const,
    statistics: () => [...keys.inspections.all, "statistics"] as const,
    timeseries: (metric: string) => [...keys.inspections.all, "timeseries", metric] as const,
  },
};
