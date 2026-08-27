import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "@/services/api";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // O SSE avisa quando algo muda; refetch por foco só geraria ruído.
      refetchOnWindowFocus: false,
      staleTime: 30_000,
      retry: (failureCount, error) => {
        // Erro de regra de negócio não melhora com nova tentativa.
        if (error instanceof ApiError && error.status && error.status < 500) return false;
        return failureCount < 2;
      },
    },
    mutations: { retry: false },
  },
});
