/**
 * Cliente HTTP único do projeto.
 *
 * Nenhum componente importa axios. Toda chamada passa por aqui, o que dá um
 * lugar só para baseURL, timeout, tradução de erro e, no futuro, autenticação.
 */
import axios, { AxiosError } from "axios";
import type { ApiErrorBody } from "@/types/api";

export class ApiError extends Error {
  readonly code: string;
  readonly status?: number;
  readonly details?: Record<string, unknown>;

  constructor(body: ApiErrorBody, status?: number) {
    super(body.message);
    this.name = "ApiError";
    this.code = body.code;
    this.status = status;
    this.details = body.details;
  }
}

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "/api/v1",
  timeout: 15_000,
  headers: { "Content-Type": "application/json" },
});

/**
 * Converte qualquer falha no `ApiError` com mensagem já escrita para o
 * operador. O componente exibe `error.message` sem precisar saber se o
 * problema foi HTTP, rede ou timeout.
 */
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ error?: ApiErrorBody }>) => {
    const body = error.response?.data?.error;
    if (body) {
      return Promise.reject(new ApiError(body, error.response?.status));
    }
    if (error.code === "ECONNABORTED") {
      return Promise.reject(
        new ApiError({ code: "TIMEOUT", message: "O servidor demorou para responder." }),
      );
    }
    return Promise.reject(
      new ApiError({
        code: "NETWORK_ERROR",
        message: "Sem conexão com o servidor. Verifique se o backend está no ar.",
      }),
    );
  },
);

/** URL absoluta do canal SSE — o EventSource não passa pelo axios. */
export function eventsUrl(): string {
  const base = api.defaults.baseURL ?? "/api/v1";
  return `${base.replace(/\/$/, "")}/flight/events`;
}
