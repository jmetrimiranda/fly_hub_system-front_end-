import { Button, CloseButton, Dialog, Flex, Portal } from "@chakra-ui/react";
import type { ReactNode } from "react";

interface Props {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  /** Rótulo da ação. Ausente, o modal só informa e tem apenas Fechar. */
  confirmLabel?: string;
  onConfirm?: () => void;
  confirmDisabled?: boolean;
  confirmLoading?: boolean;
  /** `danger` pinta a ação de vermelho: exclusão e qualquer coisa sem volta. */
  tone?: "default" | "danger";
  cancelLabel?: string;
  size?: "sm" | "md" | "lg" | "xl";
}

/**
 * Modal único do projeto.
 *
 * Toda ação destrutiva ou irreversível passa por aqui — iniciar coleta,
 * excluir imagens, excluir dataset, enviar ao Roboflow. Um lugar só define
 * onde fica o botão de confirmar, qual é o tom do perigoso e o que o Esc faz;
 * espalhado pelos componentes, cada tela inventaria a sua ordem de botões e o
 * operador aprenderia quatro convenções em vez de uma.
 */
export function Modal({
  open,
  onClose,
  title,
  children,
  confirmLabel,
  onConfirm,
  confirmDisabled = false,
  confirmLoading = false,
  tone = "default",
  cancelLabel = "Cancelar",
  size = "md",
}: Props) {
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(event) => !event.open && onClose()}
      size={size}
      placement="center"
    >
      <Portal>
        <Dialog.Backdrop />
        <Dialog.Positioner>
          <Dialog.Content bg="bg.surface" borderWidth="1px" borderColor="border.subtle">
            <Dialog.Header>
              <Dialog.Title fontSize="md" fontWeight="700">
                {title}
              </Dialog.Title>
              <Dialog.CloseTrigger asChild>
                <CloseButton size="sm" aria-label="Fechar" />
              </Dialog.CloseTrigger>
            </Dialog.Header>
            <Dialog.Body>{children}</Dialog.Body>
            <Dialog.Footer>
              <Flex gap={2} justify="flex-end" width="100%">
                <Button size="sm" variant="outline" onClick={onClose}>
                  {cancelLabel}
                </Button>
                {confirmLabel && onConfirm && (
                  <Button
                    size="sm"
                    colorPalette={tone === "danger" ? "red" : "teal"}
                    disabled={confirmDisabled}
                    loading={confirmLoading}
                    onClick={onConfirm}
                  >
                    {confirmLabel}
                  </Button>
                )}
              </Flex>
            </Dialog.Footer>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  );
}
