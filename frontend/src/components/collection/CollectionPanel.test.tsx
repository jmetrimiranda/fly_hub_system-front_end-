import { fireEvent, render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { system } from "@/theme";
import type { CollectionPreflight } from "@/types/api";
import { CollectionPanel } from "./CollectionPanel";

// O painel consulta a guarda e a coleta atual pelos hooks; o teste troca a
// camada de serviço, que é a fronteira onde a rede entra. Assim o que roda é o
// componente de verdade, com o TanStack Query no meio, e não uma imitação dele.
const getCollectionPreflight = vi.fn();
const getCurrentCollection = vi.fn();

vi.mock("@/services/api", () => ({
  flightService: {
    getCollectionPreflight: () => getCollectionPreflight(),
    getCurrentCollection: () => getCurrentCollection(),
    startCollection: vi.fn(),
    pauseCollection: vi.fn(),
    resumeCollection: vi.fn(),
    saveCollection: vi.fn(),
    cancelCollection: vi.fn(),
  },
}));

const preflight = (overrides: Partial<CollectionPreflight> = {}): CollectionPreflight => ({
  ok: true,
  checks: [
    { key: "stream", label: "Stream", ok: true, blocking: true, detail: "live/m4td", fix: null },
    { key: "mediamtx", label: "MediaMTX", ok: true, blocking: true, detail: "no ar", fix: null },
    { key: "tunnel", label: "Túnel", ok: true, blocking: false, detail: "dispensado", fix: null },
    { key: "disk", label: "Disco", ok: true, blocking: true, detail: "31% usado", fix: null },
  ],
  failed: [],
  next_version: "v0.3",
  disk_percent: 31,
  disk_free_bytes: 10_000_000_000,
  disk_limit_pct: 90,
  defaults: {
    interval_seconds: 2,
    interval_options: [0.5, 1, 2, 5],
    frame_limit: 500,
    dedup: true,
    dedup_threshold: 2,
  },
  ...overrides,
});

const streamDown = () => {
  const failing = {
    key: "stream",
    label: "Stream",
    ok: false,
    blocking: true,
    detail: "nenhum path ativo",
    fix: "Confira o endereço no FlightHub e religue o toggle do canal.",
  };
  const base = preflight();
  return preflight({
    ok: false,
    checks: [failing, ...base.checks.slice(1)],
    failed: [failing],
  });
};

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ChakraProvider value={system}>
        <CollectionPanel />
      </ChakraProvider>
    </QueryClientProvider>,
  );
}

describe("CollectionPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getCurrentCollection.mockResolvedValue(null);
  });

  it("enquanto a guarda não respondeu, o botão não acusa nada", async () => {
    // Uma promessa que nunca resolve: o estado de carregamento fica parado.
    getCollectionPreflight.mockReturnValue(new Promise(() => {}));
    renderPanel();

    expect(await screen.findByText(/Verificando as condições da coleta/)).toBeInTheDocument();
    expect(screen.queryByText(/Indicadores em vermelho/)).not.toBeInTheDocument();
  });

  it("com o stream vermelho, o modal lista o que falta e o que fazer", async () => {
    getCollectionPreflight.mockResolvedValue(streamDown());
    renderPanel();

    // A guarda precisa ter respondido: antes disso o botão está em espera e não
    // afirma nada sobre os indicadores.
    await screen.findByText(/Indicadores em vermelho/);
    fireEvent.click(screen.getByRole("button", { name: /Coletar imagens do voo/ }));

    expect(await screen.findByText("Não é possível iniciar a coleta")).toBeInTheDocument();
    expect(screen.getByText(/nenhum path ativo/)).toBeInTheDocument();
    expect(
      screen.getByText(/Confira o endereço no FlightHub e religue o toggle do canal./),
    ).toBeInTheDocument();
    // O modal de confirmação NÃO abre: a guarda não é decorativa.
    expect(screen.queryByText(/Intervalo de amostragem/)).not.toBeInTheDocument();
  });

  it("com tudo verde, abre o modal de confirmação com os parâmetros editáveis", async () => {
    getCollectionPreflight.mockResolvedValue(preflight());
    renderPanel();

    await screen.findByText(/Grava os quadros originais em v0.3/);
    fireEvent.click(screen.getByRole("button", { name: /Coletar imagens do voo/ }));

    expect(await screen.findByText(/Coletar imagens do voo · v0.3/)).toBeInTheDocument();
    expect(screen.getByText("Intervalo de amostragem")).toBeInTheDocument();
    expect(screen.getByText("Limite de quadros")).toBeInTheDocument();
    expect(screen.getByText("Descartar quadros repetidos")).toBeInTheDocument();
    expect(screen.getByDisplayValue("500")).toBeInTheDocument();
  });

  it("gravando, mostra os descartes por dedup junto dos quadros salvos", async () => {
    getCollectionPreflight.mockResolvedValue(preflight());
    getCurrentCollection.mockResolvedValue({
      id: 1,
      version: "v0.2",
      status: "recording",
      started_at: "2026-08-28T14:00:00Z",
      ended_at: null,
      duration_seconds: 40,
      image_count: 18,
      disk_bytes: 1_200_000,
      storage_path: "/data/datasets/v0.2",
      sample_interval_seconds: 2,
      frame_limit: 500,
      dedup_enabled: true,
      dedup_skipped: 7,
      progress: {
        saved: 18,
        bytes: 1_200_000,
        elapsed_seconds: 40,
        dedup_skipped: 7,
        stale_skipped: 0,
        io_dropped: 0,
        write_errors: 0,
        queue_depth: 0,
        last_file: "000018_t36.00.jpg",
        paused_reason: null,
        error: null,
        disk_percent: 31,
        disk_free_bytes: 10_000_000_000,
        disk_over_limit: false,
      },
    });

    renderPanel();

    expect(await screen.findByText("GRAVANDO")).toBeInTheDocument();
    // Sem esta linha, 25 amostras viram 18 arquivos sem explicação.
    expect(screen.getByText("Descartados (repetidos)")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Pausar/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Salvar/ })).toBeInTheDocument();
  });

  it("pausada, oferece Continuar e explica o motivo da pausa automática", async () => {
    getCollectionPreflight.mockResolvedValue(preflight());
    getCurrentCollection.mockResolvedValue({
      id: 1,
      version: "v0.2",
      status: "paused",
      started_at: "2026-08-28T14:00:00Z",
      ended_at: null,
      duration_seconds: 40,
      image_count: 500,
      disk_bytes: 1_200_000,
      storage_path: "/data/datasets/v0.2",
      sample_interval_seconds: 2,
      frame_limit: 500,
      dedup_enabled: true,
      dedup_skipped: 7,
      progress: {
        saved: 500,
        bytes: 1_200_000,
        elapsed_seconds: 40,
        dedup_skipped: 7,
        stale_skipped: 0,
        io_dropped: 0,
        write_errors: 0,
        queue_depth: 0,
        last_file: null,
        paused_reason: "limite de 500 quadros atingido",
        error: null,
        disk_percent: 31,
        disk_free_bytes: 10_000_000_000,
        disk_over_limit: false,
      },
    });

    renderPanel();

    expect(await screen.findByText("PAUSADO")).toBeInTheDocument();
    expect(screen.getByText("limite de 500 quadros atingido")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Continuar/ })).toBeInTheDocument();
  });
});
