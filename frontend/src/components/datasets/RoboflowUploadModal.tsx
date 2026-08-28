import { useEffect, useState } from "react";
import { Field, Flex, Input, NativeSelect, Switch, Text } from "@chakra-ui/react";
import { Modal } from "@/components/ui/Modal";
import { useRoboflowCredentials } from "@/hooks/useDatasets";
import type { RoboflowUploadInput } from "@/types/api";

const NEW_CREDENTIAL = "nova";

/**
 * Envio ao Roboflow: credencial, batch e tags.
 *
 * A lista suspensa traz as credenciais salvas — rótulo, workspace e projeto.
 * A chave **não** vem junto, nem mascarada: escolher uma credencial salva
 * significa que o backend a decifra na hora do envio, e a tela nunca a vê.
 *
 * `batch_name` e as tags levam a versão do dataset porque são a única resposta
 * possível quando alguém perguntar, meses depois, de qual voo veio determinada
 * imagem.
 */
export function RoboflowUploadModal({
  open,
  onClose,
  onConfirm,
  version,
  pending,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: (payload: RoboflowUploadInput) => void;
  version: string;
  pending: boolean;
}) {
  const credentials = useRoboflowCredentials();
  const [choice, setChoice] = useState(NEW_CREDENTIAL);
  const [label, setLabel] = useState("");
  const [workspace, setWorkspace] = useState("");
  const [project, setProject] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [save, setSave] = useState(true);
  const [batch, setBatch] = useState(version);
  const [tags, setTags] = useState(`${version}, drone`);

  const saved = credentials.data ?? [];
  // O id da primeira credencial, não a lista: o array é recriado a cada
  // revalidação e reabriria o formulário no meio da digitação.
  const firstCredentialId = saved[0]?.id ?? null;

  // Reabrir volta ao estado limpo, e a chave digitada não sobrevive ao
  // fechamento: ela não tem por que ficar em memória do navegador depois disso.
  useEffect(() => {
    if (!open) return;
    setChoice(firstCredentialId === null ? NEW_CREDENTIAL : String(firstCredentialId));
    setLabel("");
    setWorkspace("");
    setProject("");
    setApiKey("");
    setSave(true);
    setBatch(version);
    setTags(`${version}, drone`);
  }, [open, version, firstCredentialId]);

  const creating = choice === NEW_CREDENTIAL;
  const selected = saved.find((item) => String(item.id) === choice);
  const incomplete = creating && !(workspace.trim() && project.trim() && apiKey.trim());

  const submit = () => {
    const tagList = tags
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean);
    onConfirm(
      creating
        ? {
            workspace: workspace.trim(),
            project: project.trim(),
            api_key: apiKey,
            save_credential: save,
            label: label.trim() || undefined,
            batch_name: batch.trim() || undefined,
            tags: tagList,
          }
        : {
            credential_id: Number(choice),
            batch_name: batch.trim() || undefined,
            tags: tagList,
          },
    );
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Enviar ${version} ao Roboflow`}
      confirmLabel="Enviar"
      confirmDisabled={incomplete}
      confirmLoading={pending}
      onConfirm={submit}
    >
      <Flex direction="column" gap={5}>
        <Text fontSize="sm" color="fg.muted">
          Cada imagem sobe com a partição já decidida aqui (<code>split=train|valid|test</code>).
          Deixar o Roboflow dividir desfaria o split temporal: a divisão dele é aleatória.
        </Text>

        <Field.Root>
          <Field.Label fontSize="sm">Credencial</Field.Label>
          <NativeSelect.Root size="sm">
            <NativeSelect.Field
              value={choice}
              onChange={(event) => setChoice(event.currentTarget.value)}
            >
              {saved.map((item) => (
                <option key={item.id} value={String(item.id)}>
                  {item.label} — {item.workspace}/{item.project}
                </option>
              ))}
              <option value={NEW_CREDENTIAL}>Inserir uma nova…</option>
            </NativeSelect.Field>
            <NativeSelect.Indicator />
          </NativeSelect.Root>
          {selected && (
            <Field.HelperText fontSize="xs">
              Workspace e projeto vêm da credencial. A chave fica no servidor, cifrada.
            </Field.HelperText>
          )}
        </Field.Root>

        {creating && (
          <>
            <Field.Root>
              <Field.Label fontSize="sm">Workspace</Field.Label>
              <Input
                size="sm"
                value={workspace}
                onChange={(event) => setWorkspace(event.target.value)}
              />
            </Field.Root>
            <Field.Root>
              <Field.Label fontSize="sm">Projeto</Field.Label>
              <Input
                size="sm"
                value={project}
                onChange={(event) => setProject(event.target.value)}
              />
            </Field.Root>
            <Field.Root>
              <Field.Label fontSize="sm">Chave da API</Field.Label>
              <Input
                size="sm"
                type="password"
                autoComplete="off"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
              />
              <Field.HelperText fontSize="xs">
                Cifrada antes de tocar o banco. Nenhuma tela e nenhum endpoint a devolvem depois.
              </Field.HelperText>
            </Field.Root>
            <Field.Root>
              <Switch.Root
                checked={save}
                onCheckedChange={(event) => setSave(event.checked)}
                colorPalette="teal"
                size="sm"
              >
                <Switch.HiddenInput />
                <Switch.Control />
                <Switch.Label fontSize="sm">Guardar para os próximos envios</Switch.Label>
              </Switch.Root>
              {save && (
                <Input
                  size="sm"
                  mt={2}
                  placeholder="Como chamar esta credencial"
                  value={label}
                  onChange={(event) => setLabel(event.target.value)}
                />
              )}
            </Field.Root>
          </>
        )}

        <Field.Root>
          <Field.Label fontSize="sm">Nome do lote</Field.Label>
          <Input size="sm" value={batch} onChange={(event) => setBatch(event.target.value)} />
        </Field.Root>

        <Field.Root>
          <Field.Label fontSize="sm">Etiquetas</Field.Label>
          <Input size="sm" value={tags} onChange={(event) => setTags(event.target.value)} />
          <Field.HelperText fontSize="xs">
            Separadas por vírgula. A versão do dataset é o que liga a imagem ao voo de origem
            quando alguém perguntar meses depois.
          </Field.HelperText>
        </Field.Root>
      </Flex>
    </Modal>
  );
}
