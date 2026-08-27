import { api } from "./client";
import type { DatasetSummary, Page, RoboflowUploadResult } from "@/types/api";

export const datasetService = {
  list: (page = 1, pageSize = 50) =>
    api
      .get<Page<DatasetSummary>>("/datasets", { params: { page, page_size: pageSize } })
      .then((r) => r.data),

  get: (id: number) => api.get<DatasetSummary>(`/datasets/${id}`).then((r) => r.data),

  /**
   * Dispara o envio. A partição train/valid/test já vem pronta do backend —
   * o frontend nunca divide dataset.
   */
  sendToRoboflow: (id: number) =>
    api.post<RoboflowUploadResult>(`/datasets/${id}/roboflow`).then((r) => r.data),
};
