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

/**
 * Troca de resolução no meio da transmissão. Acontece com a qualidade do canal
 * em "Automático" no FlightHub e é a causa mais comum de queda da captura — a
 * tela avisa enquanto o servidor mandar isto preenchido.
 */
export interface ResolutionChange {
  previous: string;
  current: string;
  at: string;
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
  /** Preenchido só no terceiro estado: havia pesos, mas a carga falhou. */
  model_error: string | null;
  resolution_change: ResolutionChange | null;
  /** Motivo da última desconexão do leitor; `null` enquanto há sinal. */
  stream_error: string | null;
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

/**
 * Uma das condições que a coleta exige. `fix` é o que o modal mostra quando
 * `ok` é falso — dizer "Stream ✕" sem dizer o que fazer deixa quem está em
 * campo adivinhando.
 *
 * `blocking: false` marca condição informativa. O túnel é a única: ele deixou
 * de ser obrigatório quando o endereço público fixo entrou.
 */
export interface PreflightCheck {
  key: string;
  label: string;
  ok: boolean;
  blocking: boolean;
  detail: string;
  fix: string | null;
}

export interface CollectionDefaults {
  interval_seconds: number;
  interval_options: number[];
  frame_limit: number | null;
  dedup: boolean;
  dedup_threshold: number;
}

export interface CollectionPreflight {
  ok: boolean;
  checks: PreflightCheck[];
  failed: PreflightCheck[];
  next_version: string;
  disk_percent: number;
  disk_free_bytes: number;
  disk_limit_pct: number;
  defaults: CollectionDefaults;
}

/** Parâmetros do modal de confirmação. `frame_limit: null` é "ilimitado". */
export interface CollectionStartParams {
  interval_seconds: number;
  frame_limit: number | null;
  dedup: boolean;
}

/**
 * Contadores ao vivo da gravação. `dedup_skipped` aparece na tela de propósito:
 * sem ele o operador conta 500 amostras, encontra 180 arquivos e passa a tarde
 * procurando o erro.
 */
export interface CollectionProgress {
  saved: number;
  bytes: number;
  elapsed_seconds: number;
  dedup_skipped: number;
  stale_skipped: number;
  io_dropped: number;
  write_errors: number;
  queue_depth: number;
  last_file: string | null;
  paused_reason: string | null;
  error: string | null;
  disk_percent: number;
  disk_free_bytes: number;
  disk_over_limit: boolean;
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
  sample_interval_seconds: number;
  frame_limit: number | null;
  dedup_enabled: boolean;
  dedup_skipped: number;
  /** Preenchido só enquanto o gravador está no ar. */
  progress: CollectionProgress | null;
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
  embargo_frames: number;
  embargoed: number;
}

/** Contagem **do disco**, contada na hora. Diverge do manifesto após exclusões. */
export interface SplitCounts {
  train: number;
  valid: number;
  test: number;
  raw: number;
  total: number;
}

export interface SplitWarning {
  code: string;
  /** `error` significa dataset que não serve para medir o modelo. */
  level: "warn" | "error";
  message: string;
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

export interface DatasetDetail extends DatasetSummary {
  storage_path: string;
  ended_at: string | null;
  roboflow_error: string | null;
  sample_interval_seconds: number;
  frame_limit: number | null;
  dedup_enabled: boolean;
  dedup_skipped: number;
  split_at: string | null;
  counts: SplitCounts;
  warnings: SplitWarning[];
  /** O disco não bate mais com o manifesto: houve exclusão desde o split. */
  drifted: boolean;
}

export interface DatasetImage {
  id: number;
  filename: string;
  captured_at: string;
  frame_number: number;
  width: number | null;
  height: number | null;
  size_bytes: number;
  split: SplitName | null;
  embargoed: boolean;
  roboflow_sent_at: string | null;
  /**
   * Tamanho real. Só no visor — a grade usa `thumb_url`.
   *
   * O backend devolve caminho (`/api/v1/…`); `datasetService.images` resolve
   * os dois contra a base da API antes de entregar ao hook, porque caminho num
   * `<img src>` é resolvido contra a origem da página — o Vite na 5173, em
   * desenvolvimento — e não contra a API.
   */
  url: string;
  thumb_url: string;
}

export interface DeleteImagesResult {
  removed: number;
  counts: SplitCounts;
  distribution: SplitDistribution;
  drifted: boolean;
}

export interface ResplitResult {
  version: string;
  counts: SplitCounts;
  distribution: SplitDistribution;
  warnings: SplitWarning[];
}

/**
 * A credencial como ela sai da API. Note o que **não** está aqui: a chave.
 * Nem inteira, nem os últimos quatro caracteres — não existe endpoint que a
 * devolva.
 */
export interface RoboflowCredential {
  id: number;
  label: string;
  workspace: string;
  project: string;
  created_at: string;
  last_used_at: string | null;
}

export interface RoboflowCredentialInput {
  label: string;
  workspace: string;
  project: string;
  api_key: string;
}

export interface RoboflowUploadInput {
  credential_id?: number | null;
  workspace?: string;
  project?: string;
  api_key?: string;
  save_credential?: boolean;
  label?: string;
  batch_name?: string;
  tags?: string[];
}

export interface RoboflowUploadResult {
  dataset_id: number;
  status: RoboflowStatus;
  uploaded: number;
  failed: number;
  pending: number;
  total: number;
  batch_name: string | null;
  tags: string[];
  current_file: string | null;
  message: string | null;
  active: boolean;
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
