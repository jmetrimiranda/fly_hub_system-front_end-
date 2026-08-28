/**
 * Hooks do modelo de visão.
 *
 * O estado do modelo muda **sem** ninguém clicar em nada: alguém copia o
 * `best.pt` para `models/` e o backend percebe. Quem avisa a tela é o evento
 * SSE `model.changed` (ver `useServerEvents`), e por isso não há polling
 * agressivo aqui — só a rede de segurança de 30 s, para o caso de o canal cair.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { modelService } from "@/services/api";
import { keys } from "@/lib/queryKeys";

export function useModel() {
  return useQuery({
    queryKey: keys.model.state(),
    queryFn: modelService.get,
    refetchInterval: 30_000,
  });
}

/**
 * `toggle` e `reload` são mutações distintas de propósito, espelhando a
 * separação do backend: uma liga e desliga a inferência mantendo os pesos em
 * memória, a outra relê o disco. Um botão só faria as duas coisas e tornaria
 * impossível o teste "mesmo voo, com e sem detecção".
 */
export function useModelControls() {
  const queryClient = useQueryClient();
  // O badge sobre o vídeo lê `flight.status`, e o painel Pipeline lê a sua
  // própria chave: ligar a inferência muda os três.
  const onSuccess = () => {
    queryClient.invalidateQueries({ queryKey: keys.model.all });
    queryClient.invalidateQueries({ queryKey: keys.flight.status() });
    queryClient.invalidateQueries({ queryKey: keys.flight.pipeline() });
  };

  return {
    toggle: useMutation({ mutationFn: (enabled: boolean) => modelService.toggle(enabled), onSuccess }),
    reload: useMutation({ mutationFn: modelService.reload, onSuccess }),
  };
}
