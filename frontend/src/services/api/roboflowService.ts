import { api } from "./client";
import type { RoboflowCredential, RoboflowCredentialInput } from "@/types/api";

/**
 * Credenciais salvas do Roboflow.
 *
 * A chave sobe uma vez, no `create`, e nunca mais desce: `list` devolve
 * rótulo, workspace, projeto e último uso. Não existe método aqui que leia a
 * chave de volta, porque não existe endpoint que a devolva — nem inteira, nem
 * mascarada. Mascarada continua sendo vazamento parcial.
 */
export const roboflowService = {
  listCredentials: () =>
    api.get<RoboflowCredential[]>("/datasets/roboflow/credentials").then((r) => r.data),

  createCredential: (payload: RoboflowCredentialInput) =>
    api.post<RoboflowCredential>("/datasets/roboflow/credentials", payload).then((r) => r.data),

  deleteCredential: (id: number) =>
    api.delete<void>(`/datasets/roboflow/credentials/${id}`).then(() => undefined),
};
