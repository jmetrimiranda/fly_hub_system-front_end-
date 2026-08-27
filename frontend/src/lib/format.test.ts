import { describe, expect, it } from "vitest";
import { formatBytes, formatDuration, formatPercent } from "./format";

describe("formatDuration", () => {
  it("usa segundos abaixo de um minuto", () => {
    expect(formatDuration(40)).toBe("40 s");
  });

  it("usa minutos entre um minuto e uma hora", () => {
    expect(formatDuration(1260)).toBe("21 min");
  });

  it("quebra em horas e minutos acima de uma hora", () => {
    expect(formatDuration(3900)).toBe("1 h 5 min");
  });
});

describe("formatBytes", () => {
  it("escala até a unidade legível", () => {
    expect(formatBytes(6_396_313)).toBe("6.1 MB");
  });
});

describe("formatPercent", () => {
  it("usa vírgula decimal", () => {
    expect(formatPercent(0.324)).toBe("32,4%");
  });
});
