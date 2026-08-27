import { ChakraProvider } from "@chakra-ui/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";
import { system } from "@/theme";
import { ColorModeProvider } from "@/theme/color-mode";
import { queryClient } from "@/lib/queryClient";
import { router } from "@/routes";

export function App() {
  return (
    <ChakraProvider value={system}>
      <ColorModeProvider>
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} />
        </QueryClientProvider>
      </ColorModeProvider>
    </ChakraProvider>
  );
}
