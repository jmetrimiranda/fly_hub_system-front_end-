import { render, screen, waitFor } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { system } from "@/theme";
import { api } from "@/services/api";
import type { DatasetImage, Page } from "@/types/api";
import { ImageGallery } from "./ImageGallery";

/**
 * O defeito que este arquivo existe para pegar não está na listagem: ela
 * respondia certo o tempo todo. Estava na montagem do `src` — o backend devolve
 * `/api/v1/…`, e um caminho num `<img>` é resolvido contra a origem da página,
 * que em desenvolvimento é o Vite na 5173. O navegador recebia o `index.html`
 * do Vite onde esperava JPEG e não desenhava nada.
 *
 * Por isso o dublê fica no axios, e não em `@/services/api` como nos outros
 * testes de componente: é justamente o service que resolve o endereço. Mocá-lo
 * devolveria a URL já pronta e o teste passaria com a tela quebrada.
 */
const BASE = api.defaults.baseURL;

const image = (id: number, frame: number): DatasetImage => ({
  id,
  filename: `00000${frame}_t${frame * 2}.00.jpg`,
  captured_at: "2026-08-28T15:42:30.456991Z",
  frame_number: frame,
  width: 960,
  height: 720,
  size_bytes: 47417,
  split: "train",
  embargoed: false,
  roboflow_sent_at: null,
  // Exatamente como sai do backend: caminho, não endereço completo.
  url: `/api/v1/datasets/13/images/${id}/raw`,
  thumb_url: `/api/v1/datasets/13/images/${id}/thumb`,
});

const page: Page<DatasetImage> = {
  items: [image(3016, 1), image(3017, 2)],
  total: 2,
  page: 1,
  page_size: 60,
};

const renderGallery = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <ChakraProvider value={system}>
      <QueryClientProvider client={client}>
        <ImageGallery datasetId={13} split="train" />
      </QueryClientProvider>
    </ChakraProvider>,
  );
};

/** A origem contra a qual o navegador realmente resolveria o atributo. */
const resolvedOrigin = (element: Element) =>
  new URL(element.getAttribute("src") ?? "", window.location.href).origin;

beforeEach(() => {
  // Desenvolvimento: página no Vite (5173), API na 8000. É a configuração em
  // que o defeito aparece; com as duas no mesmo host ele fica invisível.
  api.defaults.baseURL = "http://localhost:8000/api/v1";
  vi.spyOn(api, "get").mockResolvedValue({ data: page });
});

afterEach(() => {
  api.defaults.baseURL = BASE;
  vi.restoreAllMocks();
});

describe("ImageGallery", () => {
  it("a miniatura aponta para a API, não para a origem da página", async () => {
    renderGallery();

    const thumbs = await screen.findAllByRole("img");

    expect(thumbs).toHaveLength(2);
    expect(thumbs[0].getAttribute("src")).toBe(
      "http://localhost:8000/api/v1/datasets/13/images/3016/thumb",
    );
    // O que o navegador faz com o atributo. Com um caminho relativo isto seria
    // a origem do Vite, que responde index.html e nunca uma imagem.
    expect(resolvedOrigin(thumbs[0])).toBe("http://localhost:8000");
    expect(resolvedOrigin(thumbs[1])).toBe("http://localhost:8000");
  });

  it("a grade pede /thumb, nunca o arquivo inteiro", async () => {
    renderGallery();

    const thumbs = await screen.findAllByRole("img");

    // Quinhentas imagens em tamanho real são 23 MB; em miniatura, cerca de 4.
    for (const thumb of thumbs) {
      expect(thumb.getAttribute("src")).toMatch(/\/thumb$/);
      expect(thumb.getAttribute("src")).not.toMatch(/\/raw$/);
    }
  });

  it("o visor abre a imagem em tamanho real, também absoluta", async () => {
    renderGallery();

    const thumbs = await screen.findAllByRole("img");
    thumbs[0].click();

    await waitFor(() => {
      const full = screen
        .getAllByRole("img")
        .find((element) => element.getAttribute("src")?.endsWith("/raw"));
      expect(full).toBeDefined();
      expect(full!.getAttribute("src")).toBe(
        "http://localhost:8000/api/v1/datasets/13/images/3016/raw",
      );
      expect(resolvedOrigin(full!)).toBe("http://localhost:8000");
    });
  });

  it("com página e API no mesmo host, o endereço continua relativo", async () => {
    // Produção: o nginx serve o SPA e faz proxy de /api/ para o backend.
    // Prefixar com origem aqui seria o erro simétrico.
    api.defaults.baseURL = "/api/v1";

    renderGallery();

    const thumbs = await screen.findAllByRole("img");

    expect(thumbs[0].getAttribute("src")).toBe("/api/v1/datasets/13/images/3016/thumb");
  });
});
