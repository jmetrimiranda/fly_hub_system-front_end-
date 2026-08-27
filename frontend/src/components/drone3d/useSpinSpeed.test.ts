import { describe, expect, it } from "vitest";
import { SPIN, bladePresence } from "./useSpinSpeed";

describe("bladePresence", () => {
  it("mantém a pá inteira enquanto ela ainda lê como rotação", () => {
    expect(bladePresence(0)).toBe(1);
    expect(bladePresence(SPIN.BLADE_CUTOFF_RAD_S)).toBe(1);
  });

  it("apaga a pá quando o disco já assumiu", () => {
    expect(bladePresence(SPIN.BLADE_FADE_END_RAD_S)).toBe(0);
    expect(bladePresence(SPIN.MAX_RAD_S)).toBe(0);
  });

  it("cruza monotonicamente entre os dois limiares", () => {
    const middle = (SPIN.BLADE_CUTOFF_RAD_S + SPIN.BLADE_FADE_END_RAD_S) / 2;
    expect(bladePresence(middle)).toBeCloseTo(0.5, 5);

    const start = SPIN.BLADE_CUTOFF_RAD_S;
    const step = (SPIN.BLADE_FADE_END_RAD_S - start) / 10;
    for (let i = 0; i < 10; i += 1) {
      expect(bladePresence(start + i * step)).toBeGreaterThan(
        bladePresence(start + (i + 1) * step),
      );
    }
  });

  it("nunca sai de [0, 1], inclusive com velocidade negativa", () => {
    for (const speed of [-100, -1, 0, 7.9, 8, 11, 14, 26, 1000]) {
      const presence = bladePresence(speed);
      expect(presence).toBeGreaterThanOrEqual(0);
      expect(presence).toBeLessThanOrEqual(1);
    }
  });
});
