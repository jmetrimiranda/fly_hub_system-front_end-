# Modo de teste: vídeo local alternando com o stream ao vivo

## Contexto

A tela Voo mostra o stream do drone. Para demonstrar a aplicação sem drone
disponível — ou quando o operador não está em campo — é preciso um vídeo de
exemplo que passe pelo mesmo caminho: leitor → detector → MJPEG.

Hoje isso exige publicar um stream sintético com ffmpeg, o que não serve para
demonstração: depende de um terminal aberto e de alguém saber o comando.

## Objetivo

Um botão na tela Voo alterna entre **ao vivo** e **vídeo de teste**. Com o modo
de teste ativo, o MJPEG serve quadros de um arquivo local em laço; desativado,
volta ao stream do MediaMTX.

## Decisões já tomadas

**Arquivo local, não path alternativo no MediaMTX.** O objetivo é funcionar sem
nenhuma dependência externa. Um `.mp4` no disco cumpre isso; um path alternativo
exigiria ffmpeg publicando.

**O modo de teste desliga sozinho quando o drone conecta.** Alguém vai esquecer
ligado, e olhar vídeo gravado achando que é voo ao vivo é o pior erro possível
numa tela de inspeção. Ao detectar que o stream real ficou disponível, sair do
modo de teste e registrar no log.

**A interface nunca deixa dúvida sobre qual é qual.** Ver-se-á abaixo.

## Onde fica o vídeo

```
backend/data/samples/
├── README.md          instruções, versionado
├── .gitkeep
└── voo-exemplo.mp4    ← ignorado pelo Git
```

`backend/data/samples/*.mp4` entra no `.gitignore`, pela mesma razão dos pesos:
vídeo é binário grande e todo clone pagaria por ele.

Verifique se `/workspaces/flyhub_connecting` tem algum vídeo de amostra que
possa ser reaproveitado — ele é read-only, então copie, não referencie.

Se o arquivo não existir, o modo de teste fica **indisponível**: o botão aparece
desabilitado com explicação de onde colocar o vídeo. Não invente placeholder nem
falhe silenciosamente.

## Backend

```
GET  /api/v1/flight/test-mode     estado atual, disponibilidade do arquivo
POST /api/v1/flight/test-mode     {enabled: bool}
```

O estado persiste em `app_settings`, como o toggle do modelo. Reiniciar o backend
não pode deixar a aplicação em modo de teste sem ninguém saber — mas também não
pode ligá-lo sozinho. Ao subir, se o modo estava ativo e o stream real está
disponível, sair do modo de teste.

Em `integrations/vision/`, a fonte de quadros passa a ter duas implementações
atrás da mesma interface: o leitor RTSP que já existe e um leitor de arquivo que
percorre o `.mp4` em laço, respeitando o FPS original. O `VideoService` escolhe
qual usar; o resto da cadeia — detector, MJPEG, coleta — não muda.

O evento SSE `flight.test_mode` avisa a interface quando o modo muda, inclusive
quando o desligamento é automático.

## Interface

Botão no card de vídeo da tela Voo, junto ao badge de modo. Rótulo claro:
**Vídeo de teste** ligado/desligado.

Com o modo ativo, a tela precisa gritar que não é ao vivo:

- Faixa persistente sobre o vídeo: `VÍDEO DE TESTE — NÃO É O VOO AO VIVO`
- Borda de destaque no player, em cor de aviso
- Os quatro cards de status ficam esmaecidos, com nota de que refletem o stream
  real e não o vídeo em exibição

Se o arquivo não existir, botão desabilitado com tooltip explicando o caminho.

## Coleta durante o modo de teste

**Bloquear.** O `preflight` recusa iniciar coleta com modo de teste ativo, com a
mensagem no formato dos outros bloqueios: o que impede e o que fazer.

Motivo: um dataset gerado de vídeo de exemplo entraria no banco indistinguível
de uma coleta real, e acabaria em treinamento. É o mesmo problema que a marcação
`source` resolveu para o seed.

## Restrições

- `/workspaces/flyhub_connecting` é read-only.
- Nenhum `fetch`/`axios` fora de `services/api/`; nenhum caminho `/api/` montado
  à mão em componente — o ESLint bloqueia.
- Chaves de cache só em `lib/queryKeys.ts`.
- Rotas finas; regra em service.
- Sem `localStorage`/`sessionStorage`.
- A cadeia detector → MJPEG não muda. Só a origem dos quadros.

## Como verificar

```bash
cd backend  && pytest -q
cd frontend && npm run lint && npx tsc --noEmit && npm test
```

Roteiro manual:

1. Sem `voo-exemplo.mp4`: botão desabilitado, com explicação
2. Com o arquivo: ligar o modo troca o vídeo em segundos, faixa de aviso aparece
3. Cards de status esmaecidos e anotados
4. Coletar imagens fica bloqueado, com motivo claro
5. Desligar volta ao stream real
6. Com modo ativo e stream real chegando: desliga sozinho, registra no log
7. Reiniciar o backend com stream disponível não deixa em modo de teste

Testes novos:

- Estado persiste em `app_settings`
- Desligamento automático quando o stream real fica disponível
- `preflight` recusa coleta em modo de teste
- Arquivo ausente reporta indisponível sem lançar exceção

## Pronto quando

- [ ] Toggle funcionando nos dois sentidos
- [ ] Impossível confundir vídeo de teste com voo ao vivo
- [ ] Coleta bloqueada durante o modo de teste
- [ ] Desligamento automático ao detectar stream real
- [ ] Arquivo ausente tratado com clareza
- [ ] Testes, lint e tsc passam
- [ ] `docs/flight.md` documenta o modo e onde colocar o vídeo
