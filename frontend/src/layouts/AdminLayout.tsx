import { Box, Flex } from "@chakra-ui/react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { useServerEvents } from "@/hooks/useServerEvents";

/**
 * Casca da aplicação.
 *
 * O canal SSE é assinado uma vez, aqui — não por página. Assim a telemetria
 * continua chegando enquanto o usuário navega, e não há quatro EventSources
 * abertos ao mesmo tempo.
 */
export function AdminLayout() {
  useServerEvents();

  return (
    <Flex minH="100dvh" bg="bg.canvas">
      <Sidebar />
      <Box as="main" flex="1" minW={0} px={{ base: 4, md: 8 }} py={{ base: 6, md: 8 }}>
        <Topbar />
        <Outlet />
      </Box>
    </Flex>
  );
}
