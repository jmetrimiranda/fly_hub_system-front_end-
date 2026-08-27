# Publicação da documentação

## Restrição

A infraestrutura de TI da empresa bloqueia páginas hospedadas diretamente em
Git. GitHub Pages, portanto, não serve — o código continua no Git, mas a
documentação precisa de um domínio que passe pela política de acesso.

## Recomendação: Cloudflare Pages

| Critério | Cloudflare Pages |
| --- | --- |
| Custo | Gratuito, builds ilimitados no plano free |
| Domínio | `*.pages.dev` ou domínio próprio da empresa |
| Build | Conecta ao repositório, roda `mkdocs build` |
| Bloqueio corporativo | Domínio genérico de CDN, raramente em blocklist |
| Acesso restrito | Cloudflare Access permite exigir login corporativo |

A vantagem decisiva sobre as alternativas é o **domínio próprio**: apontar
`docs.suaempresa.com.br` para o Pages resolve o bloqueio de forma definitiva,
porque o domínio é da própria empresa.

### Configuração

1. Cloudflare Dashboard → Workers & Pages → Create → Pages → Connect to Git.
2. Build command: `pip install mkdocs-material mkdocs-mermaid2-plugin mkdocs-glightbox && mkdocs build`
3. Output directory: `site`
4. Variável de ambiente: `PYTHON_VERSION = 3.12`

Cada push na `main` republica.

## Alternativas

| Serviço | Prós | Contras |
| --- | --- | --- |
| **Netlify** | Simples, plano free generoso | Domínio `netlify.app` é bloqueado com certa frequência |
| **Vercel** | Excelente DX | Otimizado para app, não para site estático de docs |
| **Read the Docs** | Feito para documentação, versionamento nativo | `readthedocs.io` costuma estar em blocklist corporativa |
| **Servidor interno** | Sem bloqueio possível | Exige infraestrutura e manutenção |

## Plano B sem depender de rede

O MkDocs gera um site estático. Se todos os serviços externos estiverem
bloqueados:

```bash
make docs-build          # gera ./site
```

O diretório `site/` abre direto no navegador (`file://`) e pode ser distribuído
por rede interna ou compactado. Não é a solução ideal — perde a busca
server-side e exige distribuição manual — mas garante que ninguém fique sem
documentação por causa de firewall.

## CI sugerido

```yaml
# .github/workflows/docs.yml
name: docs
on:
  push:
    branches: [main]
    paths: ["docs/**", "mkdocs.yml"]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install mkdocs-material mkdocs-mermaid2-plugin mkdocs-glightbox
      - run: mkdocs build --strict
      - uses: cloudflare/pages-action@v1
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          projectName: flyhub-docs
          directory: site
```

`--strict` transforma link quebrado em erro de build. Documentação com link
morto perde a confiança de quem a lê.
