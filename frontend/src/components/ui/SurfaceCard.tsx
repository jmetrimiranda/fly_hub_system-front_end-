import { Box, Flex, Text } from "@chakra-ui/react";
import type { ReactNode } from "react";

interface Props {
  title?: string;
  action?: ReactNode;
  children: ReactNode;
  padding?: number;
  height?: string | number;
}

/** Container padrão de tudo que é bloco de conteúdo. Um só lugar define sombra e raio. */
export function SurfaceCard({ title, action, children, padding = 6, height }: Props) {
  return (
    <Box
      bg="bg.surface"
      rounded="card"
      shadow="card"
      borderWidth="1px"
      borderColor="border.subtle"
      p={padding}
      height={height}
      display="flex"
      flexDirection="column"
      minW={0}
    >
      {(title || action) && (
        <Flex align="center" justify="space-between" mb={4} gap={3}>
          {title && (
            <Text fontSize="md" fontWeight="700" letterSpacing="-0.01em">
              {title}
            </Text>
          )}
          {action}
        </Flex>
      )}
      <Box flex="1" minW={0}>
        {children}
      </Box>
    </Box>
  );
}
