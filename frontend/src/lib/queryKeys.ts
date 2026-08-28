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
    preflight: () => [...keys.flight.all, "preflight"] as const,
    pipeline: () => [...keys.flight.all, "pipeline"] as const,
  },
  datasets: {
    all: ["datasets"] as const,
    list: (page: number) => [...keys.datasets.all, "list", page] as const,
    detail: (id: number) => [...keys.datasets.all, "detail", id] as const,
    // Sob `detail` de propósito: excluir imagem muda o detalhe, e invalidar
    // `detail(id)` precisa derrubar a galeria junto. Se `images` fosse irmã de
    // `detail`, a grade continuaria mostrando a imagem recém-excluída.
    images: (id: number, split: string, page: number) =>
      [...keys.datasets.detail(id), "images", split, page] as const,
    roboflow: (id: number) => [...keys.datasets.detail(id), "roboflow"] as const,
    credentials: () => [...keys.datasets.all, "credentials"] as const,
  },
  model: {
    all: ["model"] as const,
    state: () => [...keys.model.all, "state"] as const,
  },
  admin: {
    all: ["admin"] as const,
    demo: () => [...keys.admin.all, "demo"] as const,
  },
  inspections: {
    all: ["inspections"] as const,
    list: (page: number) => [...keys.inspections.all, "list", page] as const,
    statistics: () => [...keys.inspections.all, "statistics"] as const,
    timeseries: (metric: string) => [...keys.inspections.all, "timeseries", metric] as const,
  },
};
