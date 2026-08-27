/** Formatação de exibição. Nenhum componente formata número na mão. */

const dateFmt = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short" });
const dateTimeFmt = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" });
const numberFmt = new Intl.NumberFormat("pt-BR");

export const formatDate = (value: string | Date) => dateFmt.format(new Date(value));
export const formatDateTime = (value: string | Date) => dateTimeFmt.format(new Date(value));
export const formatNumber = (value: number) => numberFmt.format(value);

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)} s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  return `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(1)} ${units[unit]}`;
}

export const formatPercent = (ratio: number, digits = 1) =>
  `${(ratio * 100).toFixed(digits).replace(".", ",")}%`;
