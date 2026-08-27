import { useQuery } from "@tanstack/react-query";
import { inspectionService } from "@/services/api";
import { keys } from "@/lib/queryKeys";

export function useInspections(page = 1) {
  return useQuery({
    queryKey: keys.inspections.list(page),
    queryFn: () => inspectionService.list(page),
  });
}

export function useInspectionStatistics() {
  return useQuery({
    queryKey: keys.inspections.statistics(),
    queryFn: inspectionService.getStatistics,
  });
}

export function useInspectionTrend(metric: "count" | "damages" = "count") {
  return useQuery({
    queryKey: keys.inspections.timeseries(metric),
    queryFn: () => inspectionService.getTimeseries(metric),
  });
}
