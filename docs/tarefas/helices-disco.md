# Hélices do drone 3D: discos translúcidos com transição por velocidade

## Contexto

O `DroneModel` gira nós cujo nome case com `/prop|blade|rotor|h[ée]lice/i`. Isso
tem dois problemas.

O primeiro é de pipeline: o modelo vem do Hyper3D Rodin, e mesmo usando "Bang to
Parts" as peças saem nomeadas `part_0`, `part_1`… Depender do nome torna a cena
refém de como o exportador batizou os objetos.

O segundo é de percepção, e é o que decide a solução. Hélice de drone gira a
~5000 RPM. A 60 fps isso é mais de uma volta por quadro — impossível de
representar girando geometria. Mesmo a 26 rad/s, que é a velocidade artística
atual, são 25° por quadro; com pá de 180° de simetria isso já está no limite do
que lê como rotação contínua. Acelerar produz efeito de roda girando para trás.

Simuladores resolvem isso trocando a pá por um disco translúcido acima de um
limiar de velocidade. É o que o olho vê na realidade e não estroba, porque não há
geometria girando.

## Objetivo

O visualizador anima corretamente em qualquer velocidade e **não depende** de o
modelo ter hélices separadas ou nomeadas.

## Arquivos envolvidos

| Arquivo | O que muda |
| --- | --- |
| `frontend/src/components/drone3d/PropellerDiscs.tsx` | Novo. Quatro discos translúcidos animados. |
| `frontend/src/components/drone3d/DroneModel.tsx` | Passa a compor com os discos; detecção de hélice vira opcional. |
| `frontend/src/components/drone3d/DronePlaceholder.tsx` | Usa o mesmo componente de discos, para que os dois caminhos animem igual. |
| `frontend/src/components/drone3d/useSpinSpeed.ts` | Novo. Extrai a lógica de aceleração com inércia, hoje duplicada. |
| `scripts/inspect-glb.mjs` | Novo. Lista os nós de um `.glb` para diagnóstico. |
| `docs/drone-3d.md` | Documenta a abordagem e o fluxo de exportação no Rodin. |

## Passos

1. Criar `useSpinSpeed.ts`: hook que recebe `isFlying` e devolve a velocidade
   angular atual, com `MathUtils.damp` (alvo 26 rad/s voando, 0 em solo,
   suavização 1.8). Hoje essa lógica está duplicada entre `DroneModel` e
   `DronePlaceholder`.

2. Criar `PropellerDiscs.tsx`:
   - Recebe `positions: [x, y, z][]` e `radius: number` e `speed: number`.
   - Renderiza um disco por posição (`circleGeometry` deitado no plano XZ).
   - Material `meshBasicMaterial` com `transparent`, `depthWrite={false}`,
     `side={THREE.DoubleSide}`.
   - Opacidade e escala interpolam com a velocidade: em `speed = 0` o disco é
     invisível (`opacity 0`, escala 0.6); no máximo fica em `opacity ~0.22` e
     escala 1. Use `MathUtils.mapLinear` + `clamp`.
   - O disco gira devagar (2–3 rad/s), só para não ficar estático demais — não
     precisa acompanhar a velocidade real.

3. Em `DroneModel.tsx`:
   - Manter a detecção por nome, mas torná-la opcional e sem `console.warn`
     quando não encontrar — deixou de ser problema.
   - Se encontrar hélices: girá-las apenas até `speed < 8 rad/s`, e a partir daí
     reduzir a opacidade delas (via `material.opacity`, com `transparent = true`)
     enquanto os discos entram. Fade cruzado.
   - Derivar as posições dos discos automaticamente: percorrer a cena, calcular a
     `Box3` de cada malha candidata (achatada em Y, afastada do centro no plano
     XZ) e usar o centro delas. Se a heurística não achar quatro, cair para
     posições fixas derivadas da bounding box total do modelo (quatro cantos a
     ~85% do meio-alcance em X e Z).
   - Permitir sobrescrever por prop: `propellerPositions?: [number,number,number][]`.

4. Em `DronePlaceholder.tsx`: usar `useSpinSpeed` e `PropellerDiscs` para que o
   fallback tenha exatamente a mesma leitura visual do modelo real.

5. Criar `scripts/inspect-glb.mjs`: recebe um caminho de `.glb`, imprime nome,
   tipo e bounding box de cada nó. Serve para conferir o que o Rodin exportou sem
   abrir o Blender. Usar `@gltf-transform/core`, importado dinamicamente.

6. Atualizar `docs/drone-3d.md`: registrar por que discos em vez de geometria
   girando (o cálculo do aliasing), e o fluxo no Rodin — Bang to Parts, Pack,
   exportar `.glb`, otimizar, copiar para `frontend/public/models/drone.glb`,
   definir `VITE_DRONE_MODEL_URL`.

## Restrições

- A interface pública do `DroneViewer` **não muda**: a única entrada continua
  sendo `isFlying`. A página segue chamando `<DroneViewer isFlying={...} />`.
- Nada dentro de `components/drone3d/` pode importar hooks de dados, services ou
  tipos da API. A cena não conhece o backend.
- Respeitar `prefers-reduced-motion`: com a preferência ativa, sem flutuação nem
  rotação de órbita; os discos aparecem estáticos, apenas indicando o estado.
- Não usar `localStorage` nem `sessionStorage`.
- Nenhuma dependência nova em `package.json` além de `@gltf-transform/core` como
  `devDependency`, usada só pelo script de inspeção.

## Como verificar

```bash
cd frontend
npm run lint          # esperado: sem erros
npx tsc --noEmit      # esperado: sem erros
npm test              # esperado: passa
```

Na aplicação, com `VITE_DRONE_MODEL_URL` ausente (placeholder de blocos):

- Em solo: discos invisíveis, drone pousado, sombra nítida.
- Forçando `isFlying` para `true`: os discos surgem em ~0,8 s, o drone sobe e
  flutua, a sombra difunde.
- Sem estrobo em nenhuma velocidade.

Com o `.glb` real presente, a mesma leitura, mais o fade cruzado das pás.

Para inspecionar o arquivo exportado:

```bash
node scripts/inspect-glb.mjs frontend/public/models/drone.glb
```

## Pronto quando

- [ ] A animação funciona com `.glb` de malha única, sem aviso no console
- [ ] A animação funciona com `.glb` de peças separadas, com fade cruzado
- [ ] O placeholder e o modelo real têm a mesma leitura visual
- [ ] `prefers-reduced-motion` é respeitado
- [ ] `npm run lint` e `npx tsc --noEmit` passam
- [ ] `docs/drone-3d.md` explica a escolha e o fluxo de exportação
