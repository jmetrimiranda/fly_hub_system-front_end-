import { api, apiUrl } from "./client";
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
 * Torna utilizáveis os dois endereços que o backend devolve como caminho.
 *
 * `/api/v1/datasets/13/images/1/thumb` num `<img src>` é resolvido contra a
 * origem da *página*. Em desenvolvimento essa origem é o Vite na 5173, que
 * responde `index.html` a qualquer rota que não conheça — o navegador recebe
 * HTML no lugar de JPEG e não desenha nada, sem erro no console e sem sequer
 * uma requisição visível para a API. `apiUrl` resolve contra a base do axios,
 * a mesma fonte que o resto do projeto usa.
 *
 * A conversão fica aqui, e não no JSX, porque assim vale para todo consumidor
 * da galeria — a grade, o visor e o que vier depois.
 */
const absolutize = (image: DatasetImage): DatasetImage => ({
  ...image,
  url: apiUrl(image.url),
  thumb_url: apiUrl(image.thumb_url),
});

/**
 * Datasets: listagem, galeria, exclusão, resplit e envio ao Roboflow.
 *
 * Nenhum componente monta URL de API. A grade precisa do endereço da miniatura
 * e o visor do endereço da imagem inteira, e os dois saem do backend dentro de
 * `DatasetImage` — não de concatenação de string no JSX. O que o backend
 * devolve, porém, é caminho (`/api/v1/…`), e caminho num `<img>` é resolvido
 * contra a origem da página: resolvê-lo é o último passo desta camada, feito
 * aqui em `absolutize` para que nenhum componente precise saber disso.
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
      .then((r) => ({ ...r.data, items: r.data.items.map(absolutize) })),

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
