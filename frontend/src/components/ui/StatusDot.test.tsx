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
    expect(getComputedStyle(live!).animationName).not.toBe(
      getComputedStyle(down!).animationName,
    );
  });
});
