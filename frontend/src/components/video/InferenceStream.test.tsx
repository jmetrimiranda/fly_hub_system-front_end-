import { fireEvent, render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { describe, expect, it } from "vitest";
import { system } from "@/theme";
import type { ConnectionMetrics } from "@/types/api";
import { InferenceStream } from "./InferenceStream";

const metrics = (overrides: Partial<ConnectionMetrics> = {}): ConnectionMetrics => ({
  resolution: "960×720",
  bitrate_mbps: 0.41,
  capture_fps: 30,
  inference_fps: 30,
  latency_ms: 12,
  dropped_frames: 0,
  stream_uptime_seconds: 42,
  codec: "H264",
  model_loaded: false,
  model_enabled: true,
  model_version: null,
  model_error: null,
  resolution_change: null,
  stream_error: null,
  ...overrides,
});

const renderStream = (connected: boolean, overrides: Partial<ConnectionMetrics> = {}) =>
  render(
    <ChakraProvider value={system}>
      <InferenceStream connected={connected} metrics={metrics(overrides)} />
    </ChakraProvider>,
  );

describe("InferenceStream", () => {
  it("desconectado mantém o placeholder e não abre o stream", () => {
    renderStream(false);

    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByText(/Sem sinal/)).toBeInTheDocument();
  });

  it("conectado aponta o <img> para o endpoint MJPEG", () => {
    renderStream(true);

    const image = screen.getByRole("img");
    expect(image.getAttribute("src")).toContain("/flight/stream");
    expect(screen.getByText("Conectando ao stream…")).toBeInTheDocument();
  });

  it("sem pesos, o badge diz que o vídeo é cru", () => {
    renderStream(true);
    expect(screen.getByText("SEM MODELO — vídeo cru")).toBeInTheDocument();
  });

  it("com pesos carregados, o badge nomeia o arquivo", () => {
    renderStream(true, { model_loaded: true, model_version: "best.pt" });
    expect(screen.getByText("MODELO best.pt")).toBeInTheDocument();
  });

  it("inferência desligada não é o mesmo que não ter modelo", () => {
    // Os dois casos dão a mesma imagem — vídeo cru, sem caixa. O badge é a
    // única coisa que separa "escolhi desligar" de "não há peso nenhum".
    renderStream(true, { model_loaded: true, model_enabled: false, model_version: "best.pt" });

    expect(screen.getByText("MODELO DESLIGADO — vídeo cru")).toBeInTheDocument();
    expect(screen.queryByText("SEM MODELO — vídeo cru")).not.toBeInTheDocument();
  });

  it("pesos que existem mas não carregam são o terceiro estado", () => {
    renderStream(true, { model_error: "ultralytics indisponível" });
    expect(screen.getByText("MODELO NÃO CARREGOU — vídeo cru")).toBeInTheDocument();
  });

  it("erro no stream vira mensagem tratada, não imagem quebrada", () => {
    renderStream(true, { stream_error: "stream interrompido" });

    fireEvent.error(screen.getByRole("img"));

    expect(screen.getByText(/stream interrompido/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Tentar novamente/ })).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("tentar de novo reabre a conexão com uma URL diferente", () => {
    renderStream(true);
    const first = screen.getByRole("img").getAttribute("src");

    fireEvent.error(screen.getByRole("img"));
    fireEvent.click(screen.getByRole("button", { name: /Tentar novamente/ }));

    const retried = screen.getByRole("img").getAttribute("src");
    expect(retried).not.toBe(first);
    expect(retried).toContain("tentativa=1");
  });
});
