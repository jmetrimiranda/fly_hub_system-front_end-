import { api } from "./client";
import type {
  DatasetDetail,
  DatasetImage,
  DatasetSummary,
  DeleteImagesResult,
  Page,
  ResplitResult,
  RoboflowUploadInput,
  RoboflowUploadResult,
  SplitName,
} from "@/types/api";

/**
 * Datasets: listagem, galeria, exclusão, resplit e envio ao Roboflow.
 *
 * Nenhum componente monta URL de API. A grade precisa do endereço da miniatura
 * e o visor do endereço da imagem inteira, e os dois saem do backend dentro de
 * `DatasetImage` — não de concatenação de string no JSX.
 */
export const datasetService = {
  list: (page = 1, pageSize = 50) =>
    api
      .get<Page<DatasetSummary>>("/datasets", { params: { page, page_size: pageSize } })
      .then((r) => r.data),

  get: (id: number) => api.get<DatasetDetail>(`/datasets/${id}`).then((r) => r.data),

  /** Imagens **originais**, filtradas por partição. Nunca saída do modelo. */
  images: (id: number, split?: SplitName, page = 1, pageSize = 60) =>
    api
      .get<Page<DatasetImage>>(`/datasets/${id}/images`, {
        params: { split, page, page_size: pageSize },
      })
      .then((r) => r.data),

  /**
   * Exclusão individual ou em lote — o mesmo endpoint, porque a diferença é
   * só o tamanho da lista. Apaga da partição e de `raw/`, sem volta.
   */
  deleteImages: (id: number, imageIds: number[]) =>
    api
      .post<DeleteImagesResult>(`/datasets/${id}/images/delete`, { image_ids: imageIds })
      .then((r) => r.data),

  /** Refaz a partição a partir de `raw/`. É o que faz as proporções voltarem a valer. */
  resplit: (id: number) =>
    api.post<ResplitResult>(`/datasets/${id}/resplit`).then((r) => r.data),

  /** `confirm` é a versão digitada pelo operador. O backend confere. */
  remove: (id: number, confirm: string) =>
    api.post<void>(`/datasets/${id}/delete`, { confirm }).then(() => undefined),

  /**
   * Dispara o envio e volta na hora. A partição train/valid/test já vem pronta
   * do backend — o frontend nunca divide dataset.
   */
  sendToRoboflow: (id: number, payload: RoboflowUploadInput = {}) =>
    api.post<RoboflowUploadResult>(`/datasets/${id}/roboflow`, payload).then((r) => r.data),

  roboflowStatus: (id: number) =>
    api.get<RoboflowUploadResult>(`/datasets/${id}/roboflow`).then((r) => r.data),

  cancelRoboflow: (id: number) =>
    api.post<RoboflowUploadResult>(`/datasets/${id}/roboflow/cancel`).then((r) => r.data),
};
