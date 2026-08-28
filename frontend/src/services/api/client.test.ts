import { afterEach, describe, expect, it } from "vitest";
import { api, apiUrl, eventsUrl } from "./client";

const BASE = api.defaults.baseURL;

afterEach(() => {
  api.defaults.baseURL = BASE;
});

describe("apiUrl", () => {
  it("com a API noutra porta, o caminho do backend vira endereço absoluto", () => {
    // É a configuração de desenvolvimento: página no Vite (5173), API na 8000.
    api.defaults.baseURL = "http://localhost:8000/api/v1";

    expect(apiUrl("/api/v1/datasets/13/images/3016/thumb")).toBe(
      "http://localhost:8000/api/v1/datasets/13/images/3016/thumb",
    );
  });

  it("não duplica o prefixo já presente no caminho", () => {
    api.defaults.baseURL = "http://localhost:8000/api/v1";

    expect(apiUrl("/api/v1/datasets/13/images/3016/raw")).not.toContain("/api/v1/api/v1");
  });

  it("caminho relativo à base é somado a ela", () => {
    api.defaults.baseURL = "http://localhost:8000/api/v1";

    expect(apiUrl("/flight/stream")).toBe("http://localhost:8000/api/v1/flight/stream");
  });

  it("base relativa mantém o endereço relativo — é o caso do nginx em produção", () => {
    // Lá página e API saem do mesmo host e `VITE_API_BASE_URL` não é definida:
    // prefixar com origem alguma seria errado.
    api.defaults.baseURL = "/api/v1";

    expect(apiUrl("/api/v1/datasets/13/images/3016/thumb")).toBe(
      "/api/v1/datasets/13/images/3016/thumb",
    );
    expect(apiUrl("/flight/events")).toBe("/api/v1/flight/events");
  });

  it("API montada sob um subcaminho preserva o subcaminho", () => {
    api.defaults.baseURL = "https://interno.exemplo/flyhub/api/v1";

    expect(apiUrl("/api/v1/datasets/13/images/3016/thumb")).toBe(
      "https://interno.exemplo/flyhub/api/v1/datasets/13/images/3016/thumb",
    );
  });

  it("endereço que já é completo passa intacto", () => {
    api.defaults.baseURL = "http://localhost:8000/api/v1";

    expect(apiUrl("https://cdn.exemplo/imagem.jpg")).toBe("https://cdn.exemplo/imagem.jpg");
    expect(apiUrl("blob:http://localhost:5173/abc")).toBe("blob:http://localhost:5173/abc");
  });

  it("o canal SSE sai da mesma base", () => {
    api.defaults.baseURL = "http://localhost:8000/api/v1";

    expect(eventsUrl()).toBe("http://localhost:8000/api/v1/flight/events");
  });
});
