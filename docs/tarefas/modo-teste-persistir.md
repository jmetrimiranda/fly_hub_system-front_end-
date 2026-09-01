# O modo de teste desliga cedo demais

## O problema

O vigia desliga o modo de teste assim que o stream real fica disponível. Com o
drone transmitindo, isso acontece segundos depois de ligar — o vídeo de teste
mal aparece e some.

Isso torna o modo inútil no caso mais comum: demonstrar a aplicação enquanto o
drone está no ar.

## O que estava certo na intenção

A proteção existe porque alguém vai esquecer o modo ligado, e olhar vídeo
gravado achando que é voo ao vivo é o pior erro possível numa tela de inspeção.
Isso continua valendo.

O erro foi não distinguir dois casos diferentes:

- **Alguém acabou de ligar** — é uma decisão consciente e deve valer até que a
  mesma pessoa desligue, tenha stream real ou não.
- **Ficou ligado de antes** — ninguém decidiu nada; é resíduo de uma sessão
  anterior, e é isso que precisa morrer sozinho.

## A correção

**Ligar manualmente mantém ligado.** Enquanto o modo estiver ativo por ação do
usuário, o vigia não interfere. Só o mesmo botão desliga.

**A limpeza acontece no início da aplicação, não durante.** Ao subir o backend,
se o modo estava ativo e o stream real está disponível, sair do modo e registrar
no log. É o momento certo: ninguém está olhando, e é exatamente o cenário do
esquecimento entre sessões.

Remova o `watch()` contínuo. A proteção passa a ser a verificação no start.

## Consequência que precisa ser assumida

Com isso, é possível ficar em modo de teste com o drone ao vivo por tempo
indeterminado. É aceitável **porque a interface avisa o tempo todo** — faixa
sobre o vídeo, borda de aviso, marca no HUD, cards esmaecidos. Já foi feito.

Se ao usar ficar claro que o aviso não é suficiente, o problema é o aviso, não
o desligamento automático. Não reintroduza o vigia.

## Como verificar

```bash
cd backend  && pytest -q
cd frontend && npm run lint && npx tsc --noEmit && npm test
```

Roteiro manual, com o drone transmitindo:

1. Ligar o modo de teste — o vídeo troca e **permanece** por minutos
2. Desligar — volta ao stream real
3. Ligar de novo, reiniciar o backend com o stream disponível — sobe fora do
   modo de teste, com registro no log

Testes a ajustar: os que verificavam o desligamento durante a execução passam a
verificar o desligamento no start.

## Pronto quando

- [ ] Ligado manualmente permanece até ser desligado manualmente
- [ ] Reiniciar com stream disponível sai do modo de teste
- [ ] Avisos de interface intactos
- [ ] Testes, lint e tsc passam
- [ ] `docs/flight.md` atualizado
