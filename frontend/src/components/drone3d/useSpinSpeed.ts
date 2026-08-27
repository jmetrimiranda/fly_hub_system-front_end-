/**
 * Velocidade angular das hélices, com inércia.
 *
 * Estava duplicada entre `DroneModel` e `DronePlaceholder`, e as duas cópias
 * precisam concordar: o placeholder e o modelo real têm de ter a mesma leitura
 * visual, senão trocar um pelo outro muda a percepção da tela.
 *
 * Devolve uma `ref`, não um número de estado. A velocidade muda a cada quadro;
 * publicá-la como estado do React re-renderizaria a árvore a 60 Hz.
 */
import { useRef } from "react";
import type { RefObject } from "react";
import { useFrame } from "@react-three/fiber";
import { MathUtils } from "three";
import { usePrefersReducedMotion } from "./usePrefersReducedMotion";

export const SPIN = {
  /** Velocidade "artística" em voo. Não é RPM real — ver docs/drone-3d.md. */
  MAX_RAD_S: 26,
  /** Constante do `damp`: ligar e desligar no seco parece defeito de render. */
  DAMP: 1.8,
  /**
   * Acima disto a pá passa de ~25° por quadro a 60 fps. Com pá de 180° de
   * simetria isso já lê como roda girando para trás, então ela para e o disco
   * assume.
   */
  BLADE_CUTOFF_RAD_S: 8,
  /** Fim do fade cruzado: daqui para cima só existe disco. */
  BLADE_FADE_END_RAD_S: 14,
} as const;

/**
 * Quanto da pá ainda aparece: 1 abaixo do corte, 0 depois do fade.
 * O disco usa o complemento, e é isso que faz a troca ser cruzada.
 */
export function bladePresence(speed: number): number {
  const faded = MathUtils.mapLinear(
    speed,
    SPIN.BLADE_CUTOFF_RAD_S,
    SPIN.BLADE_FADE_END_RAD_S,
    0,
    1,
  );
  return 1 - MathUtils.clamp(faded, 0, 1);
}

export function useSpinSpeed(isFlying: boolean): RefObject<number> {
  const speed = useRef(0);
  const reduced = usePrefersReducedMotion();

  useFrame((_state, delta) => {
    const target = isFlying ? SPIN.MAX_RAD_S : 0;
    // Com movimento reduzido não há rampa: o disco apenas indica o estado.
    speed.current = reduced ? target : MathUtils.damp(speed.current, target, SPIN.DAMP, delta);
  });

  return speed;
}
