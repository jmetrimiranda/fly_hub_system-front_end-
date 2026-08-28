import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { system } from "@/theme";
import type { DatasetSummary, DemoDataSummary, Page } from "@/types/api";
import { DatasetsPage } from "./DatasetsPage";

/**
 * O que estes testes protegem é a distinção entre demonstração e voo.
 *
 * O erro que ela evita é caro e silencioso: sem o selo, alguém envia ao
 * Roboflow, anota e treina em cima de imagens que nunca existiram. E a remoção
 * é irreversível e atravessa três telas — por isso exige a frase digitada,
 * como excluir um dataset exige a versão.
 */
const listDatasets = vi.fn();
const demoSummary = vi.fn();
const clearDemo = vi.fn();

vi.mock("@/services/api", () => ({
  datasetService: { list: () => listDatasets() },
  adminService: {
    demoSummary: () => demoSummary(),
    clearDemo: () => clearDemo(),
  },
  roboflowService: { listCredentials: vi.fn() },
  ApiError: class extends Error {},
}));

const dataset = (version: string, source: "seed" | "collected"): DatasetSummary => ({
  id: version === "v0.0" ? 1 : 2,
  version,
  started_at: "2026-08-28T15:42:30Z",
  duration_seconds: 21,
  image_count: 11,
  disk_bytes: 512976,
  status: "saved",
  distribution: {
    train: 8,
    valid: 2,
    test: 1,
    embargo_seconds: 0,
    embargo_frames: 0,
    embargoed: 0,
  },
  roboflow_status: "never_sent",
  roboflow_sent_at: null,
  source,
});

const page: Page<DatasetSummary> = {
  items: [dataset("v0.0", "seed"), dataset("v0.8", "collected")],
  total: 2,
  page: 1,
  page_size: 50,
};

const demo: DemoDataSummary = {
  datasets: 4,
  inspections: 45,
  model_metrics: 1,
  sap_notes: 16,
};

const renderPage = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <ChakraProvider value={system}>
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <DatasetsPage />
        </MemoryRouter>
      </QueryClientProvider>
    </ChakraProvider>,
  );
};

beforeEach(() => {
  listDatasets.mockResolvedValue(page);
  demoSummary.mockResolvedValue(demo);
  clearDemo.mockResolvedValue(demo);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("DatasetsPage", () => {
  it("marca a coleta de demonstração e deixa a real sem selo", async () => {
    renderPage();

    await screen.findByText("v0.0");

    // Um selo, não dois: o normal não precisa de rótulo, o excepcional sim.
    const badges = screen.getAllByText("demonstração");
    expect(badges).toHaveLength(1);

    const row = screen.getByText("v0.8").closest("tr");
    expect(row?.textContent).not.toContain("demonstração");
  });

  it("a remoção só libera depois da frase digitada", async () => {
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: /Remover demonstração/ }));

    // Escopado ao diálogo: o botão que abriu o modal tem o mesmo rótulo, e
    // sem o escopo a asserção cairia nele — que nunca está desabilitado.
    const dialog = within(await screen.findByRole("dialog"));
    const confirm = dialog.getByRole("button", { name: "Remover demonstração" });
    expect(confirm).toBeDisabled();

    // A frase errada não serve: é uma exclusão irreversível que atravessa
    // datasets, inspeções, notas e métricas de uma vez.
    fireEvent.change(dialog.getByPlaceholderText("remover demonstração"), {
      target: { value: "remover" },
    });
    expect(confirm).toBeDisabled();
    expect(clearDemo).not.toHaveBeenCalled();

    fireEvent.change(dialog.getByPlaceholderText("remover demonstração"), {
      target: { value: "remover demonstração" },
    });
    await waitFor(() => expect(confirm).toBeEnabled());

    fireEvent.click(confirm);
    await waitFor(() => expect(clearDemo).toHaveBeenCalledTimes(1));
  });

  it("o modal diz o que vai sair, e a contagem não é a da tela", async () => {
    // A listagem mostra 1 dataset de demonstração; o resumo conta 4 datasets,
    // 45 inspeções e 16 notas. Quem confirma precisa ver o total real.
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: /Remover demonstração/ }));

    expect(await screen.findByText(/45 inspeção\(ões\)/)).toBeInTheDocument();
    expect(screen.getByText(/16 nota\(s\) SAP/)).toBeInTheDocument();
  });

  it("sem demonstração no banco, o botão não existe", async () => {
    demoSummary.mockResolvedValue({
      datasets: 0,
      inspections: 0,
      model_metrics: 0,
      sap_notes: 0,
    });

    renderPage();
    await screen.findByText("v0.8");

    expect(screen.queryByRole("button", { name: /Remover demonstração/ })).not.toBeInTheDocument();
  });
});
