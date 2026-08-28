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

/**
 * Endereço de um recurso da API para quem **não** passa pelo axios: `<img>`,
 * `<video>`, `EventSource`.
 *
 * O axios resolve `baseURL` sozinho; uma tag HTML não. Um `src="/api/v1/…"` é
 * resolvido contra a origem da *página* — que em desenvolvimento é o Vite na
 * 5173, não a API na 8000. O Vite responde o `index.html` a qualquer rota
 * desconhecida, então o navegador recebe HTML onde esperava JPEG, descarta em
 * silêncio e a requisição sequer aparece como erro. Daí a miniatura em branco.
 *
 * Aceita as duas formas que aparecem no projeto:
 *
 * - caminho relativo à base — `"/flight/events"`;
 * - caminho já com o prefixo da API — `"/api/v1/datasets/13/images/1/thumb"`,
 *   como o backend devolve em `url` e `thumb_url`.
 *
 * No segundo caso o trecho comum é reaproveitado, não duplicado. Em produção,
 * onde o nginx serve página e API no mesmo host e `VITE_API_BASE_URL` não é
 * definida, a base é relativa e o resultado continua relativo — nada muda.
 */
export function apiUrl(path: string): string {
  if (!path) return path;
  // Esquema (http:, data:, blob:) ou `//host`: já é endereço completo.
  if (/^[a-z][a-z0-9+.-]*:|^\/\//i.test(path)) return path;

  const suffix = path.startsWith("/") ? path : `/${path}`;
  const base = (api.defaults.baseURL ?? "/api/v1").replace(/\/$/, "");
  return base.slice(0, base.length - overlap(base, suffix)) + suffix;
}

/**
 * Quantos caracteres do fim da base o caminho já repete.
 *
 * A comparação é por segmento inteiro para que `/apiv1` não case com `/api`.
 * Zero quando não há repetição: o caminho é relativo à base e apenas se soma
 * a ela.
 */
function overlap(base: string, path: string): number {
  const segments = base.split("/").filter(Boolean);
  // Do maior candidato para o menor: `/api/v1` antes de `/v1`.
  for (let i = 0; i < segments.length; i += 1) {
    const candidate = `/${segments.slice(i).join("/")}`;
    if (path === candidate || path.startsWith(`${candidate}/`)) return candidate.length;
  }
  return 0;
}

/** URL do canal SSE — o EventSource não passa pelo axios. */
export function eventsUrl(): string {
  return apiUrl("/flight/events");
}
