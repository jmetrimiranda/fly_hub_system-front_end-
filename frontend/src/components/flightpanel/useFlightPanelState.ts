/**
 * A máquina de estados do painel de voo.
 *
 * Isolada do componente porque a parte difícil aqui é temporal, e testar tempo
 * dentro de uma cena 3D com Canvas é inviável. Com a máquina separada, os
 * timers falsos do Vitest cobrem toda a sequência em milissegundos.
 *
 *   grounded    --connected-------------> spinning-up
 *   spinning-up --estável por STABLE_MS-> flying
 *   flying      --após HOLD_MS----------> map
 *   qualquer    --desconectou-----------> grounded
 *   qualquer    --alternância manual----> map ou flying (trava o automático)
 */
import { useCallback, useEffect, useRef, useState } from "react";

export type PanelState = "grounded" | "spinning-up" | "flying" | "map";

export const PANEL_TIMING = {
  /** A conexão precisa se sustentar antes de contar como decolagem. */
  STABLE_MS: 3000,
  /** Tempo vendo o drone antes de o painel trocar para o mapa. */
  HOLD_MS: 5000,
} as const;

export const PANEL_LABEL: Record<PanelState, string> = {
  grounded: "EM SOLO",
  "spinning-up": "DECOLANDO",
  flying: "EM VOO",
  map: "EM VOO",
};

export interface FlightPanelState {
  state: PanelState;
  /** Entrada do `DroneViewer`: em solo é a única situação parada. */
  isFlying: boolean;
  showMap: boolean;
  label: string;
  /** Verdadeiro depois que o operador escolheu a vista à mão. */
  locked: boolean;
  toggle: () => void;
}

export function useFlightPanelState(connected: boolean): FlightPanelState {
  // Já conectado na primeira renderização entra direto no mapa: a cerimônia da
  // decolagem marca a transição, não deve ser pedágio a cada recarga.
  const [state, setState] = useState<PanelState>(() => (connected ? "map" : "grounded"));
  const [locked, setLocked] = useState(false);

  // Lido dentro dos timers sem entrar nas dependências do efeito — senão
  // alternar a vista reiniciaria a contagem que já está correndo.
  const lockedRef = useRef(locked);
  lockedRef.current = locked;

  useEffect(() => {
    if (!connected) {
      // Qualquer queda derruba na hora e zera os dois temporizadores. É isso
      // que impede o painel de piscar com sinal instável — e desconectar
      // também destrava a escolha manual.
      setState("grounded");
      setLocked(false);
      return;
    }

    setState((current) => (current === "grounded" ? "spinning-up" : current));

    const takeoff = setTimeout(() => {
      setState((current) => (current === "spinning-up" ? "flying" : current));
    }, PANEL_TIMING.STABLE_MS);

    const handover = setTimeout(() => {
      setState((current) =>
        current === "flying" && !lockedRef.current ? "map" : current,
      );
    }, PANEL_TIMING.STABLE_MS + PANEL_TIMING.HOLD_MS);

    // Timer vazado aqui troca a tela depois que o componente já saiu.
    return () => {
      clearTimeout(takeoff);
      clearTimeout(handover);
    };
  }, [connected]);

  const toggle = useCallback(() => {
    setLocked(true);
    setState((current) => (current === "map" ? "flying" : "map"));
  }, []);

  return {
    state,
    isFlying: state !== "grounded",
    showMap: state === "map",
    label: PANEL_LABEL[state],
    locked,
    toggle,
  };
}
