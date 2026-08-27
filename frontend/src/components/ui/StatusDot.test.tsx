import { render } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { describe, expect, it } from "vitest";
import { system } from "@/theme";
import { StatusDot } from "./StatusDot";

const renderDot = (tone: "live" | "down") =>
  render(
    <ChakraProvider value={system}>
      <StatusDot tone={tone} />
    </ChakraProvider>,
  );

describe("StatusDot", () => {
  it("pulsa apenas quando o estado é 'live'", () => {
    const live = renderDot("live").container.firstElementChild;
    const down = renderDot("down").container.firstElementChild;

    expect(live).toBeInTheDocument();
    expect(down).toBeInTheDocument();
    // O shorthand, não `animationName`: o cssstyle do jsdom não expande
    // `animation` em longhands, então `animationName` vem vazio nos dois.
    expect(getComputedStyle(live!).animation).not.toBe(getComputedStyle(down!).animation);
  });
});
