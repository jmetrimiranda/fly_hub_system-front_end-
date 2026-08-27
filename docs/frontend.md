# Frontend

React 19 + TypeScript + Vite. Componentes com Chakra UI v3, gráficos com
Recharts, 3D com React Three Fiber.

## Regra que organiza tudo

Nenhuma lógica de negócio dentro de componente. O que se evita:

```tsx
// ❌ impossível de testar, impossível de reusar
onClick={async () => {
  const r = await fetch("/api/v1/flight/collection/start", { method: "POST" });
  const data = await r.json();
  if (data.error) setErro(data.error.message);
  else { setColeta(data); setBotao("pausar"); }
}}
```

O que se faz:

```tsx
// ✅ o componente declara a intenção; o resto está em camadas testáveis
const controls = useCollectionControls();

<Button loading={controls.start.isPending} onClick={() => controls.start.mutate()}>
  Coletar imagens do voo
</Button>
```

A cadeia: **componente → hook → service → API client → backend**. Há uma regra
de ESLint que bloqueia importar `axios` fora de `src/services/api/`.

## Estado

Três tipos de estado, três lugares. A distinção que resolve a maior parte da
confusão é: **estado de servidor não é estado de aplicação**.

| Tipo | Ferramenta | Exemplo |
| --- | --- | --- |
| Servidor | TanStack Query | status do voo, datasets, inspeções |
| Cliente | Zustand (`uiStore`) | sidebar aberta, SSE conectado, toasts |
| Local | `useState` | texto sendo digitado no campo de endereço |

Copiar resposta de API para dentro de um store é a origem clássica de tela
desatualizada. Justificativa completa em [ADR 001](decisions/001-estado-frontend.md).

### Chaves de cache

Ficam todas em `lib/queryKeys.ts`, hierárquicas de propósito:

```ts
queryClient.invalidateQueries({ queryKey: keys.flight.all });     // status + coleta + pipeline
queryClient.invalidateQueries({ queryKey: keys.flight.status() }); // só o status
```

Invalidação errada é a falha mais comum com TanStack Query, e ela acontece
quando cada arquivo inventa a própria string.

## Tempo real

`useServerEvents()` é assinado **uma vez**, no `AdminLayout` — não por página.
Assim a telemetria continua chegando durante a navegação e não há quatro
`EventSource` abertos.

Cada evento tem um destino de invalidação declarado num mapa. Adicionar um
evento novo é uma linha, não um `switch`.

## Design system

A referência é o Purity UI: fundo claro e frio, cards brancos com sombra
difusa, cantos generosos, acento em teal.

!!! warning "Licença"
    O **Purity UI Dashboard PRO** é comercial e não pode ser usado sem compra.
    A versão gratuita é MIT. Este projeto não usa nenhum dos dois: reconstrói a
    linguagem visual com Chakra UI, que é a base sobre a qual o Purity foi
    feito. Sem dependência de template proprietário, sem risco de licença.
    Ver [ADR 005](decisions/005-design-system.md).

### Tokens

Tudo em `src/theme/index.ts`. Componente com hex escrito à mão não passa em
revisão.

| Token | Uso |
| --- | --- |
| `brand.500` | Acento primário (`#14A89D`) |
| `signal.live/down/warn/idle` | LEDs de estado |
| `bg.canvas` / `bg.surface` / `bg.viewer` | Fundos, com variante escura |
| `radii.card` (18px) / `radii.control` (12px) | Cantos |
| `textStyle="label"` | Rótulo em versalete espaçado |
| `textStyle="readout"` | Leitura de telemetria em mono tabular |

**A escolha que define a personalidade:** todo valor de telemetria usa
`JetBrains Mono` com algarismos tabulares. Quando o bitrate oscila de `0.41`
para `0.39`, o número não empurra o resto da linha. É como um painel de
instrumento se comporta, e é o detalhe que separa a interface de um protótipo.

### Modo escuro

Existe porque a página Voo é usada em campo, muitas vezes em cabine ou à noite.
O padrão é claro, seguindo a referência.

## Acessibilidade

Piso, não enfeite: foco de teclado visível, contraste conferido, e
`prefers-reduced-motion` respeitado — quem pede menos movimento não recebe o voo
do drone nem o pulso dos LEDs.

## Testes

```bash
npm run test
```

Vitest + Testing Library. A cobertura inicial mira o que quebra em silêncio:
formatação (`lib/format.test.ts`) e comportamento condicional de componente
(`StatusDot.test.tsx`).
