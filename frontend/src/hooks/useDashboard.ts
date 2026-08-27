import { useQuery } from "@tanstack/react-query";
import { dashboardService } from "@/services/api";
import { keys } from "@/lib/queryKeys";

export function useDashboardSummary() {
  return useQuery({ queryKey: keys.dashboard.summary(), queryFn: dashboardService.getSummary });
}

export function useDamageSeries() {
  return useQuery({
    queryKey: keys.dashboard.damageSeries(),
    queryFn: dashboardService.getDamageSeries,
  });
}

export function useRecentInspections(pageSize = 10) {
  return useQuery({
    queryKey: keys.dashboard.inspections(),
    queryFn: () => dashboardService.getRecentInspections(pageSize),
  });
}
