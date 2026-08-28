import { Badge } from "@chakra-ui/react";
import type { DataSource } from "@/types/api";

/**
 * Selo que marca uma linha vinda do `seed.py`.
 *
 * Discreto, mas presente em toda listagem onde demonstração e voo aparecem
 * lado a lado. Sem ele as duas fontes são indistinguíveis na tela, e o erro
 * que isso produz é caro: alguém envia ao Roboflow, anota e treina em cima de
 * imagens que nunca existiram.
 *
 * Nada é renderizado para `collected` — o normal não precisa de rótulo; o
 * excepcional, sim.
 */
export function DemoBadge({ source }: { source: DataSource }) {
  if (source !== "seed") return null;

  return (
    <Badge colorPalette="orange" variant="subtle" size="sm" title="Dado de demonstração, não é um voo real">
      demonstração
    </Badge>
  );
}
