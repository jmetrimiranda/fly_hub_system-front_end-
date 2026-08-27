/**
 * Drone de blocos, usado enquanto o .glb não está em `public/models/`.
 *
 * Existe para que o Dashboard funcione no primeiro `docker compose up`, sem
 * depender de um binário de 20 MB no repositório. A animação é a mesma do
 * modelo real, então trocar um pelo outro não muda nada acima deste arquivo.
 */
import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import type { Group, Mesh } from "three";
import { MathUtils } from "three";

const ARMS = [
  [1, 1],
  [1, -1],
  [-1, 1],
  [-1, -1],
] as const;

export function DronePlaceholder({ isFlying }: { isFlying: boolean }) {
  const group = useRef<Group>(null);
  const props = useRef<(Mesh | null)[]>([]);
  const spin = useRef(0);

  useFrame((state, delta) => {
    if (!group.current) return;
    spin.current = MathUtils.damp(spin.current, isFlying ? 26 : 0, 1.8, delta);
    props.current.forEach((propeller) => {
      if (propeller) propeller.rotation.y += spin.current * delta;
    });

    const elapsed = state.clock.elapsedTime;
    group.current.position.y = MathUtils.damp(
      group.current.position.y,
      isFlying ? 0.55 + Math.sin(elapsed * 1.4) * 0.06 : 0,
      2.2,
      delta,
    );
    group.current.rotation.z = MathUtils.damp(
      group.current.rotation.z,
      isFlying ? Math.sin(elapsed * 0.9) * 0.05 : 0,
      2,
      delta,
    );
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
        <group key={index} position={[x * 0.62, 0.02, z * 0.62]}>
          <mesh rotation={[0, Math.atan2(z, x), 0]}>
            <cylinderGeometry args={[0.045, 0.045, 0.55, 12]} />
            <meshStandardMaterial color="#334155" metalness={0.5} roughness={0.4} />
          </mesh>
          <mesh
            ref={(node) => {
              props.current[index] = node;
            }}
            position={[0, 0.16, 0]}
          >
            <boxGeometry args={[0.78, 0.014, 0.075]} />
            <meshStandardMaterial
              color="#94A3B8"
              transparent
              opacity={0.82}
              metalness={0.3}
              roughness={0.5}
            />
          </mesh>
        </group>
      ))}
    </group>
  );
}
