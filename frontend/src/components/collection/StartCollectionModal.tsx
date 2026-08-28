import { useEffect, useState } from "react";
import { Button, Field, Flex, Input, Switch, Text } from "@chakra-ui/react";
import { Modal } from "@/components/ui/Modal";
import type { CollectionPreflight, CollectionStartParams } from "@/types/api";

const UNLIMITED = "";

/**
 * Confirmação da coleta: intervalo, limite e deduplicação.
 *
 * Os rótulos falam do que o operador controla, não da implementação. É
 * "Intervalo de amostragem", não "sampler tick"; é "Descartar quadros
 * repetidos", não "dedup MAD". O número do limiar aparece no texto de apoio
 * porque quem já conhece o M4TD vai procurá-lo, mas ninguém precisa dele para
 * decidir.
 */
export function StartCollectionModal({
  open,
  onClose,
  onConfirm,
  preflight,
  pending,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: (params: CollectionStartParams) => void;
  preflight: CollectionPreflight;
  pending: boolean;
}) {
  const [interval, setInterval] = useState(preflight.defaults.interval_seconds);
  const [limit, setLimit] = useState(String(preflight.defaults.frame_limit ?? UNLIMITED));
  const [dedup, setDedup] = useState(preflight.defaults.dedup);

  // Reabrir o modal volta aos padrões do servidor: os valores da última coleta
  // não são um palpite melhor que os padrões, e ficam confusos depois de o
  // stream mudar de resolução.
  useEffect(() => {
    if (open) {
      setInterval(preflight.defaults.interval_seconds);
      setLimit(String(preflight.defaults.frame_limit ?? UNLIMITED));
      setDedup(preflight.defaults.dedup);
    }
  }, [open, preflight.defaults]);

  const parsedLimit = limit.trim() === UNLIMITED ? null : Number(limit);
  const limitInvalid = parsedLimit !== null && (!Number.isInteger(parsedLimit) || parsedLimit <= 0);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Coletar imagens do voo · ${preflight.next_version}`}
      confirmLabel="Confirmar"
      confirmDisabled={limitInvalid}
      confirmLoading={pending}
      onConfirm={() =>
        onConfirm({ interval_seconds: interval, frame_limit: parsedLimit, dedup })
      }
    >
      <Flex direction="column" gap={5}>
        <Text fontSize="sm" color="fg.muted">
          A gravação cria a versão <b>{preflight.next_version}</b> e guarda os quadros{" "}
          <b>originais</b>, antes da inferência. A partição train/valid/test acontece ao salvar.
        </Text>

        <Field.Root>
          <Field.Label fontSize="sm">Intervalo de amostragem</Field.Label>
          <Flex gap={2} wrap="wrap">
            {preflight.defaults.interval_options.map((option) => (
              <Button
                key={option}
                size="xs"
                variant={option === interval ? "solid" : "outline"}
                colorPalette={option === interval ? "teal" : undefined}
                onClick={() => setInterval(option)}
              >
                {option.toString().replace(".", ",")} s
              </Button>
            ))}
          </Flex>
        </Field.Root>

        <Field.Root invalid={limitInvalid}>
          <Field.Label fontSize="sm">Limite de quadros</Field.Label>
          <Input
            size="sm"
            value={limit}
            inputMode="numeric"
            placeholder="ilimitado"
            onChange={(event) => setLimit(event.target.value)}
          />
          <Field.HelperText fontSize="xs">
            Vazio grava até você mandar parar. Atingido o limite, a coleta <b>pausa</b> — salvar
            dispara o split, e essa decisão é sua.
          </Field.HelperText>
          <Field.ErrorText fontSize="xs">Informe um número inteiro maior que zero.</Field.ErrorText>
        </Field.Root>

        <Field.Root>
          <Switch.Root
            checked={dedup}
            onCheckedChange={(event) => setDedup(event.checked)}
            colorPalette="teal"
            size="sm"
          >
            <Switch.HiddenInput />
            <Switch.Control />
            <Switch.Label fontSize="sm">Descartar quadros repetidos</Switch.Label>
          </Switch.Root>
          <Field.HelperText fontSize="xs">
            Com o drone pairando, quadros idênticos incham o dataset sem acrescentar informação e
            distorcem a distribuição de treino. Cada quadro é comparado com o <b>último salvo</b>;
            abaixo de {preflight.defaults.dedup_threshold} de diferença média, é descartado. O
            número de descartes aparece durante a gravação.
          </Field.HelperText>
        </Field.Root>
      </Flex>
    </Modal>
  );
}
