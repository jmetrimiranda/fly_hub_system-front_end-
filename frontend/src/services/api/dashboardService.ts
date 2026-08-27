import { api } from "./client";
import type { DashboardSummary, InspectionSummary, Page, TimePoint } from "@/types/api";

export const dashboardService = {
  getSummary: () => api.get<DashboardSummary>("/dashboard/summary").then((r) => r.data),

  getDamageSeries: () =>
    api
      .get<{ points: TimePoint[] }>("/dashboard/damage-series")
      .then((r) => r.data.points),

  getRecentInspections: (pageSize = 10) =>
    api
      .get<Page<InspectionSummary>>("/dashboard/inspections", { params: { page_size: pageSize } })
      .then((r) => r.data),
};
