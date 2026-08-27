import { describe, expect, it } from "vitest";
import { BoxGeometry, Group, Mesh, MeshBasicMaterial } from "three";
import { collectBlades, resolveLayout } from "./DroneModel";

const ARMS: [number, number][] = [
  [1, 1],
  [1, -1],
  [-1, 1],
  [-1, -1],
];

function mesh(name: string, size: [number, number, number], at: [number, number, number]) {
  const node = new Mesh(new BoxGeometry(...size), new MeshBasicMaterial());
  node.name = name;
  node.position.set(...at);
  return node;
}

/** Quadricóptero com as quatro pás separadas, como sai do Blender. */
function quadcopter() {
  const scene = new Group();
  scene.add(mesh("body", [0.85, 0.22, 1.15], [0, 0, 0]));
  ARMS.forEach(([x, z], index) => {
    scene.add(mesh(`part_${index}`, [0.78, 0.014, 0.075], [x * 0.62, 0.18, z * 0.62]));
  });
  return scene;
}

describe("resolveLayout", () => {
  it("acha as quatro hélices sem depender do nome", () => {
    const { positions, radius } = resolveLayout(quadcopter());

    expect(positions).toHaveLength(4);
    // Uma posição por quadrante, na altura do cubo do rotor.
    const quadrants = positions.map(([x, , z]) => `${Math.sign(x)}${Math.sign(z)}`);
    expect(new Set(quadrants).size).toBe(4);
    positions.forEach(([x, y, z]) => {
      expect(Math.abs(x)).toBeCloseTo(0.62, 5);
      expect(Math.abs(z)).toBeCloseTo(0.62, 5);
      expect(y).toBeCloseTo(0.18, 5);
    });
    // Raio do disco = envergadura da pá.
    expect(radius).toBeCloseTo(0.39, 5);
  });

  it("não confunde o corpo com uma hélice", () => {
    const { positions } = resolveLayout(quadcopter());
    expect(positions.some(([x, , z]) => x === 0 && z === 0)).toBe(false);
  });

  it("cai para os quatro cantos quando o modelo é malha única", () => {
    const scene = new Group();
    scene.add(mesh("part_0", [2.0, 0.3, 1.3], [0, 0, 0]));

    const { positions, radius } = resolveLayout(scene);

    expect(positions).toHaveLength(4);
    expect(new Set(positions.map(([x, , z]) => `${Math.sign(x)}${Math.sign(z)}`)).size).toBe(4);
    positions.forEach(([x, , z]) => {
      expect(Math.abs(x)).toBeCloseTo(1.0 * 0.85, 5);
      expect(Math.abs(z)).toBeCloseTo(0.65 * 0.85, 5);
    });
    expect(radius).toBeGreaterThan(0);
    // Discos vizinhos não podem se sobrepor.
    expect(radius).toBeLessThan(Math.abs(positions[0][2] - positions[1][2]) / 2);
  });

  it("ignora candidatos em número diferente de quatro", () => {
    const scene = new Group();
    scene.add(mesh("body", [0.85, 0.22, 1.15], [0, 0, 0]));
    // Um tricóptero: a heurística não deve inventar uma quarta posição.
    [
      [1, 1],
      [1, -1],
      [-1, 1],
    ].forEach(([x, z], index) => {
      scene.add(mesh(`part_${index}`, [0.78, 0.014, 0.075], [x * 0.62, 0.18, z * 0.62]));
    });

    const { positions } = resolveLayout(scene);
    expect(positions).toHaveLength(4);
    // Veio do recuo, não dos centros das pás.
    expect(positions.every(([, y]) => y === positions[0][1])).toBe(true);
  });
});

describe("collectBlades", () => {
  it("acha as pás nomeadas em qualquer profundidade", () => {
    const scene = quadcopter();
    scene.children.slice(1).forEach((node, index) => {
      node.name = ["prop_fr", "prop_rr", "prop_fl", "prop_rl"][index];
    });

    expect(collectBlades(scene).map((node) => node.name)).toEqual([
      "prop_fr",
      "prop_rr",
      "prop_fl",
      "prop_rl",
    ]);
  });

  it("fica no nó mais alto quando pai e filho casam com o padrão", () => {
    const scene = new Group();
    const rig = new Group();
    rig.name = "propellers";
    ARMS.forEach(([x, z], index) => {
      rig.add(mesh(`prop_${index}`, [0.78, 0.014, 0.075], [x * 0.62, 0.18, z * 0.62]));
    });
    scene.add(rig);

    // Girar o pai e o filho dobraria a velocidade da pá.
    expect(collectBlades(scene)).toEqual([rig]);
  });

  it("devolve vazio no modelo de malha única, sem reclamar", () => {
    const scene = new Group();
    scene.add(mesh("part_0", [2.0, 0.3, 1.3], [0, 0, 0]));

    expect(collectBlades(scene)).toEqual([]);
  });
});
