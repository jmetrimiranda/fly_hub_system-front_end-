/**
 * Malha do drone.
 *
 * O modelo veio do Hyper3D Rodin. Geradores desse tipo costumam exportar uma
 * malha única, sem as hélices como objetos separados — e sem objetos separados
 * não há o que girar. O componente lida com os dois casos: se encontrar nós
 * cujo nome case com o padrão de hélice, gira cada um; se não encontrar, avisa
 * uma vez no console e anima só o corpo.
 *
 * Para ter as hélices girando de verdade, abra o .glb no Blender, separe as
 * quatro pás e nomeie-as `prop_fl`, `prop_fr`, `prop_rl`, `prop_rr`.
 * O passo a passo está em `docs/drone-3d.md`.
 */
import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { useGLTF } from "@react-three/drei";
import type { Group, Object3D } from "three";
import { MathUtils } from "three";

const PROPELLER_PATTERN = /prop|blade|rotor|h[ée]lice/i;
const MODEL_URL = import.meta.env.VITE_DRONE_MODEL_URL ?? "/models/drone.glb";

export function DroneModel({ isFlying }: { isFlying: boolean }) {
  const group = useRef<Group>(null);
  const { scene } = useGLTF(MODEL_URL);
  const spinSpeed = useRef(0);

  const propellers = useMemo(() => {
    const found: Object3D[] = [];
    scene.traverse((node) => {
      if (PROPELLER_PATTERN.test(node.name)) found.push(node);
    });
    return found;
  }, [scene]);

  useEffect(() => {
    if (propellers.length === 0) {
      console.warn(
        "[Drone3D] Nenhuma hélice nomeada no modelo. Veja docs/drone-3d.md para separá-las no Blender.",
      );
    }
  }, [propellers.length]);

  useFrame((state, delta) => {
    if (!group.current) return;

    // A rotação acelera e desacelera com inércia — ligar e desligar no seco
    // parece defeito de render, não um drone.
    spinSpeed.current = MathUtils.damp(spinSpeed.current, isFlying ? 26 : 0, 1.8, delta);
    propellers.forEach((propeller) => {
      propeller.rotation.y += spinSpeed.current * delta;
    });

    const elapsed = state.clock.elapsedTime;
    const targetHeight = isFlying ? 0.55 + Math.sin(elapsed * 1.4) * 0.06 : 0;
    const targetTilt = isFlying ? Math.sin(elapsed * 0.9) * 0.05 : 0;

    group.current.position.y = MathUtils.damp(group.current.position.y, targetHeight, 2.2, delta);
    group.current.rotation.z = MathUtils.damp(group.current.rotation.z, targetTilt, 2, delta);
    group.current.rotation.y += (isFlying ? 0.18 : 0.05) * delta;
  });

  return (
    <group ref={group} dispose={null}>
      <primitive object={scene} scale={1} />
    </group>
  );
}

useGLTF.preload(MODEL_URL);
