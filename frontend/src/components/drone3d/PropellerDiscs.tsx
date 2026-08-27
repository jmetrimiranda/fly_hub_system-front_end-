/**
 * Discos de rotor.
 *
 * Hélice de drone gira a ~5000 RPM. A 60 fps isso passa de uma volta por
 * quadro: não existe velocidade de geometria que represente aquilo — acelerar
 * só produz o efeito de roda girando para trás. Simulador de voo resolve
 * trocando a pá por um disco translúcido acima de um limiar, que é o que o olho
 * vê na realidade e não estroba, porque não há geometria girando.
 *
 * O componente não sabe de onde vem a velocidade nem se existe um `.glb`: recebe
 * posições e desenha. É o que permite ao placeholder e ao modelo real animarem
 * igual.
 */
import { useRef } from "react";
import type { RefObject } from "react";
import { useFrame } from "@react-three/fiber";
import type { Mesh, MeshBasicMaterial } from "three";
import { DoubleSide, MathUtils } from "three";
import { SPIN } from "./useSpinSpeed";
import { usePrefersReducedMotion } from "./usePrefersReducedMotion";

const DISC = {
  /** Disco parado é invisível; encolhido, ele "abre" junto com a aceleração. */
  MIN_SCALE: 0.6,
  MAX_OPACITY: 0.22,
  /** Giro só para o disco não ficar estático demais — não acompanha a hélice. */
  IDLE_SPIN_RAD_S: 2.4,
  SEGMENTS: 48,
} as const;

/** Espelha `ink.200` do tema. Material de Three não aceita token do Chakra. */
const DISC_COLOR = "#CBD5E1";

interface Props {
  positions: [number, number, number][];
  radius: number;
  /**
   * `ref` e não número: o valor muda a cada quadro e passá-lo como prop
   * re-renderizaria a árvore a 60 Hz.
   */
  speed: RefObject<number>;
}

export function PropellerDiscs({ positions, radius, speed }: Props) {
  const discs = useRef<(Mesh | null)[]>([]);
  const reduced = usePrefersReducedMotion();

  useFrame((_state, delta) => {
    const ratio = MathUtils.clamp(speed.current / SPIN.MAX_RAD_S, 0, 1);
    const opacity = MathUtils.mapLinear(ratio, 0, 1, 0, DISC.MAX_OPACITY);
    const scale = MathUtils.mapLinear(ratio, 0, 1, DISC.MIN_SCALE, 1);

    discs.current.forEach((disc) => {
      if (!disc) return;
      // Geometria transparente invisível ainda custa draw call; some com ela.
      disc.visible = opacity > 0.002;
      if (!disc.visible) return;

      disc.scale.setScalar(scale);
      (disc.material as MeshBasicMaterial).opacity = opacity;
      if (!reduced) disc.rotation.z += DISC.IDLE_SPIN_RAD_S * delta;
    });
  });

  return (
    <>
      {positions.map((position, index) => (
        <mesh
          key={index}
          ref={(node) => {
            discs.current[index] = node;
          }}
          position={position}
          // `circleGeometry` nasce no plano XY; deitar em XZ é o plano do rotor.
          rotation={[-Math.PI / 2, 0, 0]}
          visible={false}
          scale={DISC.MIN_SCALE}
        >
          <circleGeometry args={[radius, DISC.SEGMENTS]} />
          <meshBasicMaterial
            color={DISC_COLOR}
            transparent
            opacity={0}
            depthWrite={false}
            side={DoubleSide}
            toneMapped={false}
          />
        </mesh>
      ))}
    </>
  );
}
