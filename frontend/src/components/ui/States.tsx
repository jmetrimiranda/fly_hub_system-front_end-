import { Box, Button, Flex, Spinner, Text } from "@chakra-ui/react";
import type { ReactNode } from "react";
import { ApiError } from "@/services/api";

/** Tela vazia é convite para agir, não recado de sistema. */
export function EmptyState({ title, description, action }: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <Flex direction="column" align="center" justify="center" py={12} px={6} gap={2} textAlign="center">
      <Text fontWeight="700">{title}</Text>
      {description && (
        <Text fontSize="sm" color="fg.muted" maxW="42ch">
          {description}
        </Text>
      )}
      {action && <Box mt={3}>{action}</Box>}
    </Flex>
  );
}

/**
 * Erro para o operador: o que aconteceu e o que fazer. O detalhe técnico já
 * está no log do backend — repeti-lo aqui só assusta quem está em campo.
 */
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message =
    error instanceof ApiError ? error.message : "Não foi possível carregar estas informações.";

  return (
    <Flex direction="column" align="center" justify="center" py={10} px={6} gap={3} textAlign="center">
      <Text fontWeight="700" color="signal.down">
        {message}
      </Text>
      {onRetry && (
        <Button size="sm" variant="outline" onClick={onRetry}>
          Tentar novamente
        </Button>
      )}
    </Flex>
  );
}

export function LoadingState({ label = "Carregando…" }: { label?: string }) {
  return (
    <Flex align="center" justify="center" py={10} gap={3}>
      <Spinner size="sm" color="accent.solid" />
      <Text fontSize="sm" color="fg.muted">
        {label}
      </Text>
    </Flex>
  );
}
