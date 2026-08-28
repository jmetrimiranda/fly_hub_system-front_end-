import { api } from "./client";
import type { CollectionSession, FlightStatus, PipelineState, Telemetry } from "@/types/api";

/**
 * Voo, coleta e pipeline.
 *
 * O componente chama `flightService.startCollection()` e mais nada. Onde a
 * requisição vai, o que ela envia e como o erro é traduzido é assunto desta
 * camada.
 */
export const flightService = {
  getStatus: () => api.get<FlightStatus>("/flight/status").then((r) => r.data),

  /**
   * URL do vídeo com inferência. O `<img>` do player fala direto com o
   * backend — MJPEG não passa pelo axios —, mas o endereço continua saindo
   * daqui: componente não monta string de API.
   *
   * `attempt` existe para o botão de tentar de novo: a URL precisa mudar para
   * o navegador reabrir a conexão em vez de reaproveitar a que falhou.
   */
  streamUrl: (attempt = 0): string => {
    const base = (api.defaults.baseURL ?? "/api/v1").replace(/\/$/, "");
    return attempt > 0 ? `${base}/flight/stream?tentativa=${attempt}` : `${base}/flight/stream`;
  },

  setEndpoint: (endpoint: string) =>
    api.put<FlightStatus>("/flight/endpoint", { endpoint }).then((r) => r.data),

  /**
   * Última posição conhecida, para o mapa se posicionar na montagem. Daí em
   * diante quem alimenta a tela é o evento SSE — isto não vira polling.
   * `204` significa que a fonte de voo ainda não produziu amostra alguma.
   */
  getTelemetry: (): Promise<Telemetry | null> =>
    api.get<Telemetry>("/flight/telemetry").then((r) => (r.status === 204 ? null : r.data)),

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
