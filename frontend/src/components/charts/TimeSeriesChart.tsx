import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TimePoint } from "@/types/api";
import { formatDate } from "@/lib/format";
import { axisProps, chartColors, tooltipStyle } from "./chartTheme";

interface Props {
  data: TimePoint[];
  height?: number;
  valueLabel: string;
}

/**
 * Um componente de série temporal serve as três telas: avarias por inspeção no
 * Dashboard e evolução das inspeções em Aplicação > Inspeção. Mesma leitura,
 * mesmo eixo, mesma cor — o operador aprende a ler o gráfico uma vez só.
 */
export function TimeSeriesChart({ data, height = 280, valueLabel }: Props) {
  const points = data.map((point) => ({ ...point, label: formatDate(point.date) }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={points} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
        <defs>
          <linearGradient id="seriesFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={chartColors.line} stopOpacity={0.32} />
            <stop offset="100%" stopColor={chartColors.line} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={chartColors.grid} vertical={false} />
        <XAxis dataKey="label" {...axisProps} minTickGap={28} />
        <YAxis {...axisProps} allowDecimals={false} width={40} />
        <Tooltip
          {...tooltipStyle}
          formatter={(value: number) => [value, valueLabel]}
          labelFormatter={(label: string) => label}
        />
        <Area
          type="monotone"
          dataKey="value"
          stroke={chartColors.line}
          strokeWidth={2}
          fill="url(#seriesFill)"
          activeDot={{ r: 4 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
