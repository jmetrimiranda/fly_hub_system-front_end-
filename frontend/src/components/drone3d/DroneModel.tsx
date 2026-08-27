/**
 * Malha do drone.
 *
 * O modelo vem do Hyper3D Rodin. Mesmo com "Bang to Parts" as peças saem
 * nomeadas `part_0`, `part_1`… — depender do nome deixaria a cena refém de como
 * o exportador batizou os objetos. Por isso a animação não depende disso: os
 * discos de rotor (`PropellerDiscs`) são posicionados por geometria e funcionam
 * com um `.glb` de malha única.
 *
 * Se as pás existirem separadas, elas entram como refinamento: giram enquanto a
 * velocidade é baixa e somem em fade cruzado quando o disco assume. O porquê do
 * limiar está em `useSpinSpeed.ts` e em `docs/drone-3d.md`.
 */
import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { useGLTF } from "@react-three/drei";
import type { Group, Material, Mesh, Object3D } from "three";
import { Box3, MathUtils, Vector3 } from "three";
import { PropellerDiscs } from "./PropellerDiscs";
import { SPIN, bladePresence, useSpinSpeed } from "./useSpinSpeed";
import { usePrefersReducedMotion } from "./usePrefersReducedMotion";

const PROPELLER_PATTERN = /prop|blade|rotor|h[ée]lice/i;
const MODEL_URL = import.meta.env.VITE_DRONE_MODEL_URL ?? "/models/drone.glb";

/** Hélice é achatada: a espessura é uma fração da envergadura. */
const FLATNESS = 0.5;
/** E mora longe do centro no plano XZ. O corpo e a câmera, não. */
const OFFSET = 0.35;
/** Cantos do recuo: fração do meio-alcance da bounding box total. */
const CORNER = 0.85;

type Tuple = [number, number, number];

interface Layout {
  positions: Tuple[];
  radius: number;
}

interface Fade {
  mesh: Mesh;
  original: Material | Material[];
  clones: Material[];
}

function isMesh(node: Object3D): node is Mesh {
  return (node as Mesh).isMesh === true;
}

/**
 * Onde desenhar os discos.
 *
 * Percorre a cena procurando malhas com cara de hélice — achatadas em Y e
 * afastadas do centro. Se não achar exatamente quatro, cai para os quatro
 * cantos da bounding box total, que erra pouco em qualquer quadricóptero.
 */
export function resolveLayout(scene: Object3D): Layout {
  scene.updateWorldMatrix(true, true);

  const modelBox = new Box3().setFromObject(scene);
  const size = modelBox.getSize(new Vector3());
  const center = modelBox.getCenter(new Vector3());
  const halfX = size.x / 2;
  const halfZ = size.z / 2;

  const positions: Tuple[] = [];
  const radii: number[] = [];
  const box = new Box3();
  const partSize = new Vector3();
  const partCenter = new Vector3();

  scene.traverse((node) => {
    if (!isMesh(node)) return;
    box.setFromObject(node);
    box.getSize(partSize);
    box.getCenter(partCenter);

    const flat = partSize.y < Math.min(partSize.x, partSize.z) * FLATNESS;
    const away =
      Math.abs(partCenter.x - center.x) > halfX * OFFSET &&
      Math.abs(partCenter.z - center.z) > halfZ * OFFSET;

    if (flat && away) {
      positions.push([partCenter.x, partCenter.y, partCenter.z]);
      radii.push(Math.max(partSize.x, partSize.z) / 2);
    }
  });

  if (positions.length === 4) {
    return { positions, radius: radii.reduce((a, b) => a + b, 0) / radii.length };
  }

  // Recuo: cantos a 85% do meio-alcance, no topo do corpo.
  const y = modelBox.min.y + size.y * CORNER;
  const corners: Tuple[] = [
    [1, 1],
    [1, -1],
    [-1, 1],
    [-1, -1],
  ].map(([sx, sz]) => [center.x + sx * halfX * CORNER, y, center.z + sz * halfZ * CORNER]);

  return { positions: corners, radius: Math.min(size.x, size.z) * 0.26 };
}

/**
 * Nós de hélice, só os mais altos de cada ramo.
 *
 * Um `.glb` pode ter um grupo `propellers` com filhos `prop_fl`, `prop_fr`… — o
 * padrão casa com os dois. Aplicar a rotação no pai e no filho dobraria a
 * velocidade da pá, e clonar o material duas vezes deixaria o clone preso na
 * malha no unmount.
 */
export function collectBlades(scene: Object3D): Object3D[] {
  const found: Object3D[] = [];

  scene.traverse((node) => {
    if (!PROPELLER_PATTERN.test(node.name)) return;
    for (let parent = node.parent; parent; parent = parent.parent) {
      if (found.includes(parent)) return;
    }
    found.push(node);
  });

  return found;
}

/**
 * Materiais das pás, clonados.
 *
 * Sem clonar, uma malha que compartilhe material com o corpo levaria o corpo
 * junto no fade. O original volta no cleanup e o clone é descartado.
 */
function prepareFades(nodes: Object3D[]): Fade[] {
  const fades: Fade[] = [];

  nodes.forEach((node) => {
    node.traverse((child) => {
      if (!isMesh(child)) return;
      const original = child.material;
      const clones = (Array.isArray(original) ? original : [original]).map((material) => {
        const clone = material.clone();
        clone.transparent = true;
        // `transparent` mexe no programa do shader: mudar por quadro recompila.
        clone.needsUpdate = true;
        return clone;
      });
      child.material = Array.isArray(original) ? clones : clones[0];
      fades.push({ mesh: child, original, clones });
    });
  });

  return fades;
}

interface Props {
  isFlying: boolean;
  /** Escape para quando a heurística errar em um modelo específico. */
  propellerPositions?: Tuple[];
}

export function DroneModel({ isFlying, propellerPositions }: Props) {
  const group = useRef<Group>(null);
  const { scene } = useGLTF(MODEL_URL);
  const speed = useSpinSpeed(isFlying);
  const reduced = usePrefersReducedMotion();

  // Detecção por nome continua, agora como refinamento: não achar nada deixou
  // de ser problema, então também não há mais aviso no console.
  const blades = useMemo(() => collectBlades(scene), [scene]);

  const fades = useMemo(() => prepareFades(blades), [blades]);
  const layout = useMemo(() => resolveLayout(scene), [scene]);
  const positions = propellerPositions ?? layout.positions;

  useEffect(
    () => () => {
      fades.forEach(({ mesh, original, clones }) => {
        mesh.material = original;
        clones.forEach((clone) => clone.dispose());
      });
    },
    [fades],
  );

  useFrame((state, delta) => {
    if (!group.current) return;

    const current = speed.current;
    if (current < SPIN.BLADE_CUTOFF_RAD_S) {
      blades.forEach((blade) => {
        blade.rotation.y += current * delta;
      });
    }

    const presence = bladePresence(current);
    fades.forEach(({ mesh, clones }) => {
      mesh.visible = presence > 0.002;
      clones.forEach((clone) => {
        clone.opacity = presence;
        clone.depthWrite = presence > 0.98;
      });
    });

    const elapsed = state.clock.elapsedTime;
    const height = isFlying ? 0.55 + (reduced ? 0 : Math.sin(elapsed * 1.4) * 0.06) : 0;
    const tilt = isFlying && !reduced ? Math.sin(elapsed * 0.9) * 0.05 : 0;

    if (reduced) {
      // Sem flutuação e sem órbita: a cena só indica o estado.
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
      <primitive object={scene} scale={1} />
      <PropellerDiscs positions={positions} radius={layout.radius} speed={speed} />
    </group>
  );
}

useGLTF.preload(MODEL_URL);
