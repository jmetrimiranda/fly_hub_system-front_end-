# Login antes de tudo

## Contexto

A aplicação vai ficar acessível pela internet. Hoje não há autenticação alguma:
qualquer pessoa que alcance o endereço vê o vídeo ao vivo do drone, inicia e
para coletas, apaga datasets e acessa as credenciais do Roboflow.

É preciso uma porta na frente.

## Escopo

**Uma senha única, compartilhada, para toda a aplicação.** Não há usuários,
papéis ou perfis. Quem tem a senha entra e pode tudo; quem não tem não vê nada.

Isso é deliberado — a plataforma tem um operador, e um sistema de usuários seria
peso morto. Mas registre a limitação no código e na documentação: se um dia
mais de uma pessoa usar, não há como saber quem fez o quê.

## Credenciais

Usuário `porto`, senha `31415926`.

**As duas vêm do `.env`**, não do código:

```
AUTH_USER=porto
AUTH_PASSWORD=31415926
```

Com valores de exemplo no `.env.example` e nota de que devem ser trocados.

Motivo: senha em código-fonte vai para o Git, aparece no histórico para sempre,
e é vista por qualquer um com acesso ao repositório — incluindo quem não deveria
ter acesso à aplicação. Além disso, trocar a senha não pode exigir um commit.

A senha é guardada como hash, não em texto puro. Use a biblioteca de hashing que
o projeto já tem via `cryptography`, ou `passlib` se for mais direto.

## Como funciona

Um cookie de sessão assinado, com validade de 12 horas. Ao expirar, volta para o
login.

```
POST /api/v1/auth/login     {username, password} → cookie de sessão
POST /api/v1/auth/logout    limpa o cookie
GET  /api/v1/auth/me        sessão válida? (para a interface decidir)
```

Middleware no FastAPI bloqueia todas as rotas sob `/api/v1` sem sessão válida,
com duas exceções: as próprias rotas de auth e o health check.

Atenção ao SSE e ao MJPEG: são conexões longas e precisam validar a sessão na
abertura como qualquer outra rota. Confirme que continuam funcionando.

## Limite de tentativas

Cinco tentativas erradas do mesmo IP bloqueiam novas tentativas por 15 minutos.

Sem isso, uma senha de 8 dígitos cai em minutos de tentativa automatizada — e a
aplicação estará na internet aberta. O contador pode ficar em memória; não
precisa sobreviver a reinício.

A mensagem de erro nunca distingue "usuário não existe" de "senha errada".

## Interface

Tela de login simples: dois campos, um botão, a marca do FlyHub. Nada além
disso.

Erro em texto claro, sem detalhe técnico. Quando bloqueado por tentativas, diga
quanto falta para liberar.

Toda a aplicação fica atrás dessa tela. Se a sessão expirar durante o uso, volta
para o login sem perder o que estava na tela por baixo — mas sem vazar nada
dela.

Um item discreto de sair da sessão na barra lateral, junto ao rodapé onde está
"telemetria ativa".

## Restrições

- Nenhum `fetch`/`axios` fora de `services/api/`
- Chaves de cache só em `lib/queryKeys.ts`
- Sem `localStorage`/`sessionStorage` — o cookie é `httpOnly`
- Rotas finas; regra em service
- O cookie precisa de `Secure` e `SameSite=Lax` quando servido por HTTPS

## Como verificar

```bash
cd backend  && pytest -q
cd frontend && npm run lint && npx tsc --noEmit && npm test
```

Roteiro manual:

1. Abrir a aplicação sem sessão → tela de login
2. Credenciais erradas → erro genérico
3. Cinco erros seguidos → bloqueio com tempo restante
4. Credenciais certas → entra, e o vídeo ao vivo funciona
5. SSE e MJPEG continuam funcionando autenticados
6. Sair da sessão → volta ao login
7. Chamar `/api/v1/flight/status` sem cookie → 401

Testes novos:

- Rotas protegidas recusam sem sessão
- Login com credenciais corretas emite cookie válido
- Bloqueio após cinco tentativas
- Sessão expirada é recusada

## Pronto quando

- [ ] Nada acessível sem login
- [ ] Credenciais no `.env`, senha em hash
- [ ] Limite de tentativas funcionando
- [ ] SSE e MJPEG operando autenticados
- [ ] Testes, lint e tsc passam
- [ ] `docs/` explica como trocar a senha e registra a limitação de usuário único
