import { useState } from "react";
import { Box, Button, Flex, Grid, Image, Text } from "@chakra-ui/react";
import { CheckSquare, Square, Trash2 } from "lucide-react";
import { Modal } from "@/components/ui/Modal";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { useDatasetImages, useDeleteImages } from "@/hooks/useDatasets";
import { formatBytes, formatDateTime, formatNumber } from "@/lib/format";
import type { DatasetImage, SplitName } from "@/types/api";

const PAGE_SIZE = 60;

/**
 * Grade de miniaturas de uma partição.
 *
 * A grade pede `thumb_url`, de 240 px; o visor pede `url`, o arquivo inteiro.
 * Mandar quinhentos JPEGs em tamanho real para montar uma grade trava a aba —
 * é o tipo de coisa que só aparece na primeira coleta grande de verdade, e aí
 * já é tarde.
 *
 * As imagens são as **originais**, sem inferência. Esta tela nunca mostra
 * saída do modelo: um dataset contaminado com a própria predição faz o treino
 * seguinte aprender os erros do anterior.
 */
export function ImageGallery({ datasetId, split }: { datasetId: number; split: SplitName }) {
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [viewing, setViewing] = useState<DatasetImage | null>(null);
  const [confirming, setConfirming] = useState<DatasetImage[] | null>(null);

  const images = useDatasetImages(datasetId, split, page);
  const remove = useDeleteImages(datasetId);

  if (images.isLoading) return <LoadingState />;
  if (images.isError) return <ErrorState error={images.error} onRetry={() => images.refetch()} />;

  const items = images.data?.items ?? [];
  const total = images.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  if (total === 0) {
    return (
      <EmptyState
        title={`Nenhuma imagem em ${split}`}
        description="A partição ficou vazia. Refaça o split a partir de raw/ ou colete por mais tempo."
      />
    );
  }

  const toggle = (id: number) =>
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const confirmDelete = () => {
    const targets = confirming ?? [];
    remove.mutate(
      targets.map((item) => item.id),
      {
        onSuccess: () => {
          setConfirming(null);
          setSelected(new Set());
        },
      },
    );
  };

  return (
    <>
      <Flex align="center" justify="space-between" gap={3} mb={4} wrap="wrap">
        <Text fontSize="sm" color="fg.muted">
          {formatNumber(total)} imagem(ns)
          {selected.size > 0 && ` · ${selected.size} selecionada(s)`}
        </Text>
        <Flex gap={2}>
          {selected.size > 0 && (
            <>
              <Button size="xs" variant="ghost" onClick={() => setSelected(new Set())}>
                Limpar seleção
              </Button>
              <Button
                size="xs"
                colorPalette="red"
                variant="outline"
                onClick={() => setConfirming(items.filter((item) => selected.has(item.id)))}
              >
                <Trash2 size={14} /> Excluir selecionadas
              </Button>
            </>
          )}
        </Flex>
      </Flex>

      <Grid templateColumns="repeat(auto-fill, minmax(140px, 1fr))" gap={3}>
        {items.map((item) => (
          <Thumb
            key={item.id}
            image={item}
            selected={selected.has(item.id)}
            onToggle={() => toggle(item.id)}
            onOpen={() => setViewing(item)}
          />
        ))}
      </Grid>

      {pages > 1 && (
        <Flex align="center" justify="center" gap={3} mt={5}>
          <Button size="xs" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            Anterior
          </Button>
          <Text fontSize="xs" color="fg.muted">
            {page} de {pages}
          </Text>
          <Button
            size="xs"
            variant="outline"
            disabled={page >= pages}
            onClick={() => setPage(page + 1)}
          >
            Próxima
          </Button>
        </Flex>
      )}

      {/* Visor: aqui, e só aqui, a imagem inteira é baixada. */}
      <Modal
        open={viewing !== null}
        onClose={() => setViewing(null)}
        title={viewing?.filename ?? ""}
        size="xl"
        cancelLabel="Fechar"
        confirmLabel="Excluir"
        tone="danger"
        onConfirm={() => {
          if (viewing) setConfirming([viewing]);
          setViewing(null);
        }}
      >
        {viewing && (
          <Flex direction="column" gap={3}>
            <Image
              src={viewing.url}
              alt={viewing.filename}
              maxH="60vh"
              objectFit="contain"
              rounded="card"
              bg="bg.subtle"
            />
            <Text fontSize="xs" color="fg.muted">
              Quadro #{viewing.frame_number} · {formatDateTime(viewing.captured_at)} ·{" "}
              {viewing.width}×{viewing.height} · {formatBytes(viewing.size_bytes)}
              {viewing.roboflow_sent_at && " · já enviada ao Roboflow"}
            </Text>
          </Flex>
        )}
      </Modal>

      <Modal
        open={confirming !== null}
        onClose={() => setConfirming(null)}
        title={
          confirming?.length === 1
            ? "Excluir esta imagem?"
            : `Excluir ${confirming?.length ?? 0} imagens?`
        }
        confirmLabel="Excluir"
        tone="danger"
        confirmLoading={remove.isPending}
        onConfirm={confirmDelete}
      >
        <Flex direction="column" gap={3}>
          <Text fontSize="sm">
            A exclusão apaga da partição <b>e</b> de <code>raw/</code>, e não pode ser desfeita.
          </Text>
          <Text fontSize="sm" color="fg.muted">
            Apagar só da partição faria o “Refazer split” — oferecido justamente porque as
            proporções mudam — ressuscitar tudo que você acabou de excluir.
          </Text>
          {confirming?.some((item) => item.roboflow_sent_at) && (
            <Text fontSize="sm" color="signal.warn">
              Parte destas imagens já foi enviada ao Roboflow. Excluí-las aqui não as remove de lá.
            </Text>
          )}
        </Flex>
      </Modal>
    </>
  );
}

function Thumb({
  image,
  selected,
  onToggle,
  onOpen,
}: {
  image: DatasetImage;
  selected: boolean;
  onToggle: () => void;
  onOpen: () => void;
}) {
  return (
    <Box position="relative" rounded="card" overflow="hidden" borderWidth="1px" borderColor={selected ? "accent.solid" : "border.subtle"}>
      <Image
        src={image.thumb_url}
        alt={image.filename}
        loading="lazy"
        width="100%"
        aspectRatio={4 / 3}
        objectFit="cover"
        cursor="pointer"
        bg="bg.subtle"
        onClick={onOpen}
      />
      <Box
        position="absolute"
        top="6px"
        left="6px"
        color={selected ? "accent.solid" : "fg.muted"}
        bg="bg.surface"
        rounded="sm"
        p="2px"
        cursor="pointer"
        onClick={onToggle}
        aria-label={selected ? "Desmarcar" : "Selecionar"}
        role="checkbox"
        aria-checked={selected}
      >
        {selected ? <CheckSquare size={14} /> : <Square size={14} />}
      </Box>
      <Text textStyle="readout" fontSize="10px" color="fg.muted" px={2} py={1} truncate>
        #{image.frame_number}
      </Text>
    </Box>
  );
}
