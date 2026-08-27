import { api } from "./client";
import type { CollectionSession, FlightStatus, PipelineState } from "@/types/api";

/**
 * Voo, coleta e pipeline.
 *
 * O componente chama `flightService.startCollection()` e mais nada. Onde a
 * requisição vai, o que ela envia e como o erro é traduzido é assunto desta
 * camada.
 */
export const flightService = {
  getStatus: () => api.get<FlightStatus>("/flight/status").then((r) => r.data),

  setEndpoint: (endpoint: string) =>
    api.put<FlightStatus>("/flight/endpoint", { endpoint }).then((r) => r.data),

  getCurrentCollection: () =>
    api.get<CollectionSession | null>("/flight/collection/current").then((r) => r.data),

  startCollection: () =>
    api.post<CollectionSession>("/flight/collection/start").then((r) => r.data),

  pauseCollection: () =>
    api.post<CollectionSession>("/flight/collection/pause").then((r) => r.data),

  resumeCollection: () =>
    api.post<CollectionSession>("/flight/collection/resume").then((r) => r.data),

  saveCollection: () => api.post<CollectionSession>("/flight/collection/save").then((r) => r.data),

  cancelCollection: () =>
    api.post<CollectionSession>("/flight/collection/cancel").then((r) => r.data),

  getPipeline: () => api.get<PipelineState>("/flight/pipeline").then((r) => r.data),

  startPipeline: () => api.post<PipelineState>("/flight/pipeline/start").then((r) => r.data),

  stopPipeline: () => api.post<PipelineState>("/flight/pipeline/stop").then((r) => r.data),
};
