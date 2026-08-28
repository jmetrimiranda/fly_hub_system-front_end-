import { Flex, Text } from "@chakra-ui/react";
import { Check, X } from "lucide-react";
import { Modal } from "@/components/ui/Modal";
import type { CollectionPreflight, PreflightCheck } from "@/types/api";

/**
 * O que falta para poder gravar, item a item.
 *
 * Um modal que diz só "não é possível iniciar a coleta" faz quem está em campo
 * adivinhar qual das quatro condições falhou e o que fazer com ela. Aqui cada
 * linha traz o estado, o detalhe e — quando falhou — a instrução vinda do
 * servidor, que é quem sabe o motivo.
 */
export function PreflightModal({
  open,
  onClose,
  preflight,
}: {
  open: boolean;
  onClose: () => void;
  preflight: CollectionPreflight | undefined;
}) {
  return (
    <Modal open={open} onClose={onClose} title="Não é possível iniciar a coleta" cancelLabel="Fechar">
      <Flex direction="column" gap={4}>
        {preflight?.checks.map((check) => <CheckRow key={check.key} check={check} />)}
      </Flex>
    </Modal>
  );
}

function CheckRow({ check }: { check: PreflightCheck }) {
  const failed = !check.ok && check.blocking;

  return (
    <Flex gap={3} align="flex-start">
      <Flex
        color={check.ok ? "signal.live" : failed ? "signal.down" : "signal.idle"}
        mt="2px"
        flexShrink={0}
      >
        {check.ok ? <Check size={16} /> : <X size={16} />}
      </Flex>
      <Flex direction="column" gap={1} minW={0}>
        <Text fontSize="sm" fontWeight="700">
          {check.label}
          <Text as="span" fontWeight="400" color="fg.muted">
            {" "}
            — {check.detail}
          </Text>
        </Text>
        {failed && check.fix && (
          <Text fontSize="xs" color="fg.muted">
            {check.fix}
          </Text>
        )}
      </Flex>
    </Flex>
  );
}
