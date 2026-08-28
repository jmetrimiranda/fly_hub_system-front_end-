# Como subir a aplicação

Este guia mudou de lugar: ele agora vive dentro da documentação, em
[`docs/rodar/index.md`](docs/rodar/index.md), onde o MkDocs consegue alcançá-lo
— a navegação não segue caminho para fora de `docs/`, e enquanto o arquivo
estava aqui ele simplesmente não aparecia no site.

**Para ler navegando:**

```bash
make docs        # http://localhost:8001 → Executar → Como rodar
```

**Para ler direto no repositório:**

| Documento | O que é |
| --- | --- |
| [Como rodar a aplicação](docs/rodar/index.md) | do zero ao navegador aberto, host × container, problemas conhecidos |
| [Onde colocar o peso do modelo](docs/modelo/index.md) | para quem só treina: onde o `best.pt` vai e como confirmar que carregou |
| [Fluxo de branches](docs/rodar/branches.md) | `main`, `develop`, `release` e o caminho de um peso novo até produção |

O caminho mais curto, se você só quer subir:

```bash
# 🖥️ HOST
cp .env.example .env
code .          # Ctrl+Shift+P → Dev Containers: Reopen in Container

# 🐳 CONTAINER
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

A aplicação abre em <http://localhost:5173>.
