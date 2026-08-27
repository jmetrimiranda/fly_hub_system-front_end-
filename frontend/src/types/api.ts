/**
 * Contrato da API.
 *
 * Estes tipos espelham os schemas Pydantic do backend. Quando o backend mudar,
 * rode `npm run types:api` para regenerar a partir do OpenAPI — o arquivo
 * gerado é a fonte de verdade; este aqui é a versão legível e estável usada
 * pelos componentes.
 */

export type CollectionStatus = "recording" | "paused" | "saved" | "cancelled" | "failed";
export type PipelineStatus = "stopped" | "starting" | "running" | "error";
export type RoboflowStatus = "never_sent" | "queued" | "uploading" | "sent" | "failed";
export type SplitName = "train" | "valid" | "test";
export type InspectionStatus = "processing" | "completed" | "failed";

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface ApiErrorBody {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface TimePoint {
  date: string;
  value: number;
}

/* --- Voo ------------------------------------------------------------------ */

export interface FlightIndicators {
  availability: boolean;
  mediamtx_up: boolean;
  tunnel_up: boolean;
  stream_up: boolean;
  availability_label: string;
  mediamtx_label: string;
  tunnel_label: string;
  stream_label: string;
}

export interface ConnectionMetrics {
  resolution: string | null;
  bitrate_mbps: number | null;
  capture_fps: number | null;
  inference_fps: number | null;
  latency_ms: number | null;
  dropped_frames: number;
  stream_uptime_seconds: number;
  codec: string | null;
  model_loaded: boolean;
  model_version: string | null;
}

export interface FlightStatus {
  connected: boolean;
  endpoint: string;
  publish_url: string;
  stream_path: string;
  indicators: FlightIndicators;
  metrics: ConnectionMetrics;
  last_seen_at: string | null;
}

/**
 * Uma amostra de posição. Chega pelo evento SSE `flight.telemetry`, que — única
 * exceção ao ADR 002 — carrega o dado em vez de só avisar (ver ADR 006).
 */
export interface Telemetry {
  at: string;
  latitude: number;
  longitude: number;
  /** Relativa ao ponto de decolagem, não ao nível do mar. */
  altitude_m: number;
  /** Rumo de bússola: 0 = norte, sentido horário. */
  heading_deg: number;
  horizontal_speed_ms: number;
  satellites: number;
  fix_type: "none" | "gps" | "rtk";
}

export interface CollectionSession {
  id: number;
  version: string;
  status: CollectionStatus;
  started_at: string;
  ended_at: string | null;
  duration_seconds: number;
  image_count: number;
  disk_bytes: number;
  storage_path: string;
}

export interface PipelineState {
  status: PipelineStatus;
  stream_path: string;
  started_at: string | null;
  model_loaded: boolean;
  model_version: string | null;
  message: string | null;
}

/* --- Datasets ------------------------------------------------------------- */

export interface SplitDistribution {
  train: number;
  valid: number;
  test: number;
  embargo_seconds: number;
}

export interface DatasetSummary {
  id: number;
  version: string;
  started_at: string;
  duration_seconds: number;
  image_count: number;
  disk_bytes: number;
  status: CollectionStatus;
  distribution: SplitDistribution;
  roboflow_status: RoboflowStatus;
  roboflow_sent_at: string | null;
}

export interface RoboflowUploadResult {
  dataset_id: number;
  status: RoboflowStatus;
  uploaded: number;
  failed: number;
  message: string | null;
}

/* --- Inspeções ------------------------------------------------------------ */

export interface InspectionSummary {
  id: number;
  code: string;
  inspected_at: string;
  flight_time_seconds: number;
  damage_count: number;
  open_note_count: number;
  status: InspectionStatus;
}

export interface InspectionStatistics {
  total: number;
  with_damage: number;
  without_damage: number;
  damage_ratio: number;
  average_damage_per_inspection: number;
}

/* --- Dashboard ------------------------------------------------------------ */

export interface MetricCard {
  value: number;
  label: string;
  unit: string | null;
  delta_percent: number | null;
}

export interface DashboardSummary {
  flight_connection: { connected: boolean; label: string };
  inspection_count: MetricCard;
  open_notes: MetricCard;
  mape: MetricCard;
}
