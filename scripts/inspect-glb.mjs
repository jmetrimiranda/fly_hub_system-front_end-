#!/usr/bin/env node
/**
 * Lista os nós de um .glb: nome, tipo e bounding box.
 *
 * Serve para conferir o que o Rodin exportou sem abrir o Blender — em especial
 * se as hélices saíram como objetos separados e com que nome. Diagnóstico
 * apenas: a cena não depende mais dessa resposta, porque os discos de rotor
 * funcionam com malha única. Ver docs/drone-3d.md.
 *
 *   node scripts/inspect-glb.mjs frontend/public/models/drone.glb
 */
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import { access } from "node:fs/promises";

const INSTALL_HINT =
  "@gltf-transform/core não encontrado. Instale com:\n  cd frontend && npm install";

/**
 * A dependência é devDependency do frontend, mas o script mora na raiz — a
 * resolução padrão do Node não sobe até `frontend/node_modules`.
 */
async function loadCore() {
  const candidates = [
    () => {
      const require = createRequire(new URL("../frontend/package.json", import.meta.url));
      return import(pathToFileURL(require.resolve("@gltf-transform/core")).href);
    },
    () => import("@gltf-transform/core"),
  ];

  for (const load of candidates) {
    try {
      return await load();
    } catch {
      // Tenta a próxima estratégia de resolução.
    }
  }
  throw new Error(INSTALL_HINT);
}

const fixed = (value) => (Number.isFinite(value) ? value.toFixed(3) : "—");
const vec = (v) => (v ? `[${v.map(fixed).join(", ")}]` : "—");

function describe(node, getBounds) {
  const mesh = node.getMesh();
  const primitives = mesh ? mesh.listPrimitives() : [];
  const vertices = primitives.reduce(
    (total, prim) => total + (prim.getAttribute("POSITION")?.getCount() ?? 0),
    0,
  );

  let box = null;
  try {
    const bounds = getBounds(node);
    if (bounds && bounds.min.every(Number.isFinite)) box = bounds;
  } catch {
    // Nó sem geometria alcançável: segue sem bounding box.
  }

  return {
    name: node.getName() || "(sem nome)",
    kind: mesh ? "mesh" : node.listChildren().length > 0 ? "group" : "empty",
    primitives: primitives.length,
    vertices,
    box,
  };
}

async function main() {
  const file = process.argv[2];
  if (!file) {
    console.error("uso: node scripts/inspect-glb.mjs <caminho/para/modelo.glb>");
    process.exitCode = 2;
    return;
  }

  try {
    await access(file);
  } catch {
    console.error(`Arquivo não encontrado: ${file}`);
    process.exitCode = 2;
    return;
  }

  const { NodeIO, getBounds } = await loadCore();
  const document = await new NodeIO().read(file);
  const root = document.getRoot();
  const nodes = root.listNodes();

  console.log(`\n${file}`);
  console.log(`${nodes.length} nós, ${root.listMeshes().length} malhas\n`);

  const rows = nodes.map((node) => describe(node, getBounds));
  const width = Math.max(4, ...rows.map((row) => row.name.length));

  console.log(
    `${"nome".padEnd(width)}  ${"tipo".padEnd(6)}  ${"vért.".padStart(7)}  min → max`,
  );
  console.log("─".repeat(width + 40));

  for (const row of rows) {
    const extent = row.box ? `${vec(row.box.min)} → ${vec(row.box.max)}` : "—";
    console.log(
      `${row.name.padEnd(width)}  ${row.kind.padEnd(6)}  ${String(row.vertices).padStart(7)}  ${extent}`,
    );
  }

  // A pergunta que motiva o script.
  const propellers = rows.filter((row) => /prop|blade|rotor|h[ée]lice/i.test(row.name));
  console.log(
    `\nNós com nome de hélice: ${propellers.length}` +
      (propellers.length === 4
        ? " — o fade cruzado das pás vai funcionar."
        : " — a cena usa só os discos de rotor, o que é suficiente."),
  );
}

main().catch((error) => {
  console.error(error.message ?? error);
  process.exitCode = 1;
});
