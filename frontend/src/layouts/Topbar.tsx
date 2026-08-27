import { Box, Flex, IconButton, Text } from "@chakra-ui/react";
import { Moon, Sun } from "lucide-react";
import { useLocation } from "react-router-dom";
import { useColorMode } from "@/theme/color-mode";

const TITLES: Record<string, { crumb: string; title: string }> = {
  "/": { crumb: "Dashboard", title: "Visão geral" },
  "/voo": { crumb: "Pages / Voo", title: "Conexão de voo" },
  "/datasets": { crumb: "Pages / Dataset", title: "Coletas de imagens" },
  "/inspecao": { crumb: "Aplicação / Inspeção", title: "Análise de inspeções" },
};

export function Topbar() {
  const { pathname } = useLocation();
  const { isDark, toggleColorMode } = useColorMode();
  const page = TITLES[pathname] ?? { crumb: "FlyHub", title: "" };

  return (
    <Flex as="header" align="flex-end" justify="space-between" gap={4} mb={7}>
      <Box>
        <Text textStyle="label" mb={1}>
          {page.crumb}
        </Text>
        <Text as="h1" fontSize="2xl" fontWeight="800" letterSpacing="-0.025em" lineHeight="1.1">
          {page.title}
        </Text>
      </Box>
      <IconButton
        aria-label={isDark ? "Usar modo claro" : "Usar modo escuro"}
        variant="ghost"
        size="sm"
        onClick={toggleColorMode}
      >
        {isDark ? <Sun size={18} /> : <Moon size={18} />}
      </IconButton>
    </Flex>
  );
}
