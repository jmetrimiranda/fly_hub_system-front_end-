/** Ajustes compartilhados dos gráficos, para que os três tenham a mesma voz. */
export const chartColors = {
  line: "#14A89D",
  fill: "rgba(20, 168, 157, 0.14)",
  grid: "rgba(148, 163, 184, 0.22)",
  axis: "#94A3B8",
  warn: "#F59E0B",
};

export const axisProps = {
  stroke: chartColors.axis,
  fontSize: 11,
  tickLine: false,
  axisLine: false,
} as const;

export const tooltipStyle = {
  contentStyle: {
    borderRadius: 12,
    border: "1px solid rgba(148,163,184,0.25)",
    fontSize: 12,
    fontFamily: "'JetBrains Mono', monospace",
    boxShadow: "0 12px 32px -16px rgba(15,23,42,0.4)",
  },
} as const;
