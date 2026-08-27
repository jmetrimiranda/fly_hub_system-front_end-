/**
 * Drone de blocos, usado enquanto o .glb não está em `public/models/`.
 *
 * Existe para que o Dashboard funcione no primeiro `docker compose up`, sem
 * depender de um binário de 20 MB no repositório. Compartilha `useSpinSpeed` e
 * `PropellerDiscs` com o modelo real, então a leitura visual é a mesma: pás
 * girando devagar, disco assumindo na aceleração. Trocar um pelo outro não muda
 * nada acima deste arquivo.
 */
import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import type { Group, Mesh, MeshStandardMaterial } from "three";
import { MathUtils } from "three";
import { PropellerDiscs } from "./PropellerDiscs";
import { SPIN, bladePresence, useSpinSpeed } from "./useSpinSpeed";
import { usePrefersReducedMotion } from "./usePrefersReducedMotion";

const ARM = 0.62;
const HUB_Y = 0.18;
const DISC_RADIUS = 0.42;

const ARMS = [
  [1, 1],
  [1, -1],
  [-1, 1],
  [-1, -1],
] as const;

const DISC_POSITIONS = ARMS.map(([x, z]): [number, number, number] => [
  x * ARM,
  HUB_Y,
  z * ARM,
]);

/** Opacidade da pá em repouso; o fade cruzado escala a partir daqui. */
const BLADE_OPACITY = 0.82;

export function DronePlaceholder({ isFlying }: { isFlying: boolean }) {
  const group = useRef<Group>(null);
  const blades = useRef<(Mesh | null)[]>([]);
  const speed = useSpinSpeed(isFlying);
  const reduced = usePrefersReducedMotion();

  useFrame((state, delta) => {
    if (!group.current) return;

    const current = speed.current;
    const presence = bladePresence(current);

    blades.current.forEach((blade) => {
      if (!blade) return;
      // Acima do limiar a pá para de girar: 25° por quadro já lê como estrobo.
      if (current < SPIN.BLADE_CUTOFF_RAD_S) blade.rotation.y += current * delta;
      blade.visible = presence > 0.002;
      (blade.material as MeshStandardMaterial).opacity = presence * BLADE_OPACITY;
    });

    const elapsed = state.clock.elapsedTime;
    const height = isFlying ? 0.55 + (reduced ? 0 : Math.sin(elapsed * 1.4) * 0.06) : 0;
    const tilt = isFlying && !reduced ? Math.sin(elapsed * 0.9) * 0.05 : 0;

    if (reduced) {
      group.current.position.y = height;
      group.current.rotation.z = tilt;
      return;
    }

    group.current.position.y = MathUtils.damp(group.current.position.y, height, 2.2, delta);
    group.current.rotation.z = MathUtils.damp(group.current.rotation.z, tilt, 2, delta);
    group.current.rotation.y += (isFlying ? 0.18 : 0.05) * delta;
  });

  return (
    <group ref={group} dispose={null}>
      <mesh castShadow>
        <boxGeometry args={[0.85, 0.22, 1.15]} />
        <meshStandardMaterial color="#1E293B" metalness={0.55} roughness={0.35} />
      </mesh>
      <mesh position={[0, -0.16, 0.36]} castShadow>
        <sphereGeometry args={[0.14, 24, 24]} />
        <meshStandardMaterial color="#14A89D" metalness={0.7} roughness={0.2} />
      </mesh>

      {ARMS.map(([x, z], index) => (
        <group key={index} position={[x * ARM, 0.02, z * ARM]}>
          <mesh rotation={[0, Math.atan2(z, x), 0]}>
            <cylinderGeometry args={[0.045, 0.045, 0.55, 12]} />
            <meshStandardMaterial color="#334155" metalness={0.5} roughness={0.4} />
          </mesh>
          <mesh
            ref={(node) => {
              blades.current[index] = node;
            }}
            position={[0, HUB_Y - 0.02, 0]}
          >
            <boxGeometry args={[0.78, 0.014, 0.075]} />
            <meshStandardMaterial
              color="#94A3B8"
              transparent
              opacity={BLADE_OPACITY}
              metalness={0.3}
              roughness={0.5}
            />
          </mesh>
        </group>
      ))}

      <PropellerDiscs positions={DISC_POSITIONS} radius={DISC_RADIUS} speed={speed} />
    </group>
  );
}
