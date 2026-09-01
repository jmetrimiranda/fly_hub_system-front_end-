# A aplicação em produção

## Contexto

Hoje a aplicação só existe enquanto alguém mantém terminais abertos: MediaMTX
pelo `start.sh`, backend pelo `uvicorn --reload`, frontend pelo Vite em modo de
desenvolvimento. Fechar o terminal ou reiniciar a máquina derruba tudo.

Ela precisa subir sozinha no boot e ficar acessível pela internet, com HTTPS.

## O alcance pretendido

Uma pessoa, acessando de fora — de outra cidade ou da rede corporativa do
cliente. Não é uso multiusuário nem alta disponibilidade.

O caminho de rede já está pronto: `flyhub-jorge.ddns.net` resolve para o IP de
casa, o roteador encaminha a 1935 para esta máquina, e o DDNS acompanha as
trocas de IP.

## O que muda

```
Internet
   ↓ 443
nginx  ── /        → frontend estático (build)
       └─ /api/    → backend  :8000
   ↓
systemd: mediamtx · backend · nginx
```

## Frontend em produção

`npm run build` gera os estáticos. O Vite em modo dev sai de cena — ele não é
feito para uso real, e o `--host 0.0.0.0` exposto na internet seria imprudente.

`VITE_API_BASE_URL` passa a ser relativo (`/api/v1`), servido pela mesma origem.
Isso elimina o CORS inteiro em produção — vale conferir se o middleware ainda é
necessário, e manter apenas para desenvolvimento.

## nginx

Serve os estáticos e faz proxy de `/api/` para o backend.

Duas rotas exigem atenção especial, porque o padrão do nginx as quebra:

- **MJPEG** (`/api/v1/flight/stream`) — `proxy_buffering off`, sem timeout
- **SSE** (`/api/v1/flight/events`) — mesmo tratamento, mais `proxy_read_timeout`
  longo e `X-Accel-Buffering: no`

Sem isso o vídeo trava e a telemetria para de chegar, com sintoma difícil de
diagnosticar — parece problema de aplicação.

Limite de upload compatível com o que a coleta salva.

## HTTPS

Certificado do Let's Encrypt para `flyhub-jorge.ddns.net`, via `certbot`, com
renovação automática pelo timer que ele instala.

**Isto não é opcional.** Sem HTTPS a senha e o cookie de sessão trafegam em
texto puro pela internet, e todo o trabalho de autenticação vira decoração.

Com HTTPS ativo, o cookie de sessão precisa ganhar `Secure` — hoje ele sai sem,
porque o desenvolvimento é em HTTP. Deve ser condicional ao esquema, não fixo:
`Secure` em HTTPS, sem em `localhost`. Uma variável no `.env` decide.

Redirecionar HTTP para HTTPS.

## systemd

Três unidades, em `/etc/systemd/system/`:

- `flyhub-mediamtx.service` — o MediaMTX que hoje o `start.sh` sobe
- `flyhub-backend.service` — uvicorn sem `--reload`, com workers adequados
- nginx já tem a sua

Todas com `Restart=always` e `After=network-online.target`. O backend depende do
Postgres, que continua em Docker — a unidade precisa esperar o container.

O `start.sh` do M4TD continua existindo para desenvolvimento; a unidade é o
caminho de produção. Deixe claro na documentação que não devem rodar juntos.

## Portas no roteador

Além da 1935 já configurada, encaminhar 80 e 443 para `192.168.3.38`. O certbot
precisa da 80 para validar o domínio.

**Reserva de DHCP é pré-requisito.** Se o IP local mudar, todo o encaminhamento
aponta para o vazio. Documente como fazer, com o aviso de que sem isso a
instalação quebra silenciosamente.

## O que NÃO fazer

Não exponha 8000, 5432, 8554 nem 9997 na internet. Só 443, 80 e 1935 saem para
fora; o resto fica em `localhost` ou na rede local.

## Restrições

- O que roda em Docker hoje (Postgres) continua em Docker
- Nada de segredo em arquivo versionado
- As unidades systemd leem o `.env` existente

## Como verificar

```bash
cd backend  && pytest -q
cd frontend && npm run lint && npx tsc --noEmit && npm test && npm run build
```

Roteiro manual, da rede local:

1. `sudo systemctl restart flyhub-backend` → aplicação volta sozinha
2. `https://flyhub-jorge.ddns.net` → tela de login, cadeado válido
3. Login → vídeo ao vivo funcionando **por vários minutos**, sem travar
4. Telemetria chegando continuamente (SSE atravessando o nginx)
5. `http://flyhub-jorge.ddns.net` → redireciona para HTTPS
6. Reiniciar a máquina → tudo volta sem intervenção

O passo 3 é o que mais falha. Assista de verdade, não olhe um quadro.

Da rede externa — celular em 4G serve:

7. Mesmo endereço, mesmo comportamento

## Pronto quando

- [ ] Aplicação sobe sozinha no boot
- [ ] HTTPS com certificado válido e renovação automática
- [ ] Cookie com `Secure` em produção
- [ ] MJPEG e SSE atravessando o nginx sem travar
- [ ] Acessível de fora da rede
- [ ] `docs/rodar/producao.md` com instalação, portas, DHCP e como parar tudo
- [ ] `starting_aplication.md` separa desenvolvimento de produção
