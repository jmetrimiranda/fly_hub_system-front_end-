import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PANEL_TIMING, useFlightPanelState } from "./useFlightPanelState";

const { STABLE_MS, HOLD_MS } = PANEL_TIMING;

/** Avança o relógio falso deixando o React processar o que os timers dispararam. */
function advance(ms: number) {
  act(() => {
    vi.advanceTimersByTime(ms);
  });
}

describe("useFlightPanelState", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("fica em solo enquanto ninguém conecta", () => {
    const { result } = renderHook(() => useFlightPanelState(false));

    expect(result.current.state).toBe("grounded");
    expect(result.current.isFlying).toBe(false);
    expect(result.current.label).toBe("EM SOLO");

    advance(STABLE_MS + HOLD_MS + 1000);
    expect(result.current.state).toBe("grounded");
  });

  it("não avança quando a conexão cai antes de se sustentar", () => {
    const { result, rerender } = renderHook(({ up }) => useFlightPanelState(up), {
      initialProps: { up: false },
    });

    rerender({ up: true });
    expect(result.current.state).toBe("spinning-up");
    expect(result.current.label).toBe("DECOLANDO");

    advance(STABLE_MS - 500);
    rerender({ up: false });

    expect(result.current.state).toBe("grounded");
    // O sinal instável não pode deixar a contagem antiga viva e trocar a tela.
    advance(STABLE_MS + HOLD_MS + 1000);
    expect(result.current.state).toBe("grounded");
  });

  it("percorre a sequência completa com conexão estável", () => {
    const { result, rerender } = renderHook(({ up }) => useFlightPanelState(up), {
      initialProps: { up: false },
    });

    rerender({ up: true });
    expect(result.current.state).toBe("spinning-up");

    advance(STABLE_MS);
    expect(result.current.state).toBe("flying");
    expect(result.current.label).toBe("EM VOO");
    expect(result.current.showMap).toBe(false);

    advance(HOLD_MS);
    expect(result.current.state).toBe("map");
    expect(result.current.showMap).toBe(true);
    expect(result.current.isFlying).toBe(true);
  });

  it("entra direto no mapa quando já está conectado na montagem", () => {
    const { result } = renderHook(() => useFlightPanelState(true));

    expect(result.current.state).toBe("map");
    expect(result.current.showMap).toBe(true);
  });

  it("respeita a escolha manual de ver o drone", () => {
    const { result, rerender } = renderHook(({ up }) => useFlightPanelState(up), {
      initialProps: { up: false },
    });

    rerender({ up: true });
    advance(STABLE_MS);
    expect(result.current.state).toBe("flying");

    act(() => result.current.toggle());
    expect(result.current.state).toBe("map");

    act(() => result.current.toggle());
    expect(result.current.state).toBe("flying");
    expect(result.current.locked).toBe(true);

    // Quem escolheu o drone não é arrastado de volta ao mapa.
    advance(HOLD_MS * 4);
    expect(result.current.state).toBe("flying");
  });

  it("desconectar volta ao solo e destrava o automático", () => {
    const { result, rerender } = renderHook(({ up }) => useFlightPanelState(up), {
      initialProps: { up: true },
    });

    act(() => result.current.toggle());
    expect(result.current.locked).toBe(true);

    rerender({ up: false });
    expect(result.current.state).toBe("grounded");
    expect(result.current.locked).toBe(false);

    // Reconectou: a sequência recomeça do zero, sem trava herdada.
    rerender({ up: true });
    expect(result.current.state).toBe("spinning-up");
    advance(STABLE_MS + HOLD_MS);
    expect(result.current.state).toBe("map");
  });

  it("não deixa temporizador pendente ao desmontar no meio da contagem", () => {
    const { rerender, unmount } = renderHook(({ up }) => useFlightPanelState(up), {
      initialProps: { up: false },
    });

    rerender({ up: true });
    advance(STABLE_MS - 500);
    expect(vi.getTimerCount()).toBeGreaterThan(0);

    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
});
