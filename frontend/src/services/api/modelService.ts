import { api } from "./client";
import type { ModelState } from "@/types/api";

/**
 * Modelo de visão: estado, toggle da inferência e releitura do disco.
 *
 * Nenhum método envia pesos, e não é omissão. Quem treina copia `best.pt` para
 * `models/` e a aplicação percebe sozinha; um endpoint de upload transformaria
 * uma cópia de arquivo num formulário e quebraria o contrato de cinco passos
 * de `models/README.md`.
 */
export const modelService = {
  get: () => api.get<ModelState>("/model").then((r) => r.data),

  /**
   * Liga e desliga a **inferência**, sem descarregar os pesos. É o que permite
   * comparar o mesmo voo com e sem detecção — o primeiro teste que se faz ao
   * receber um modelo novo.
   */
  toggle: (enabled: boolean) =>
    api.post<ModelState>("/model/toggle", { enabled }).then((r) => r.data),

  /** Relê o disco agora. Ação distinta do toggle: não liga nem desliga nada. */
  reload: () => api.post<ModelState>("/model/reload").then((r) => r.data),
};
