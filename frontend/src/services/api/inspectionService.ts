import { api } from "./client";
import type { InspectionStatistics, InspectionSummary, Page, TimePoint } from "@/types/api";

export const inspectionService = {
  list: (page = 1, pageSize = 50) =>
    api
      .get<Page<InspectionSummary>>("/inspections", { params: { page, page_size: pageSize } })
      .then((r) => r.data),

  getStatistics: () =>
    api.get<InspectionStatistics>("/inspections/statistics").then((r) => r.data),

  getTimeseries: (metric: "count" | "damages" = "count") =>
    api.get<TimePoint[]>("/inspections/timeseries", { params: { metric } }).then((r) => r.data),
};
