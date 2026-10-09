# dev-find

**dev-find** é um agente Python para prospecção automatizada e responsável de oportunidades profissionais em empresas de tecnologia.

Ele descobre empresas por cidade, visita apenas páginas públicas do site oficial, identifica canais corporativos de recrutamento/contato, mantém um banco SQLite para deduplicação e envia uma candidatura com CV sem repetir empresa.

## Fluxo

```text
Cidade
  -> descoberta de empresas de TI
  -> domínio/site oficial
  -> páginas públicas (carreiras, vagas, contato)
  -> e-mail corporativo público
  -> score do contato
  -> deduplicação SQLite
  -> fila de candidatura
  -> SMTP + CV
  -> empresa marcada como enviada
  -> próxima empresa
```

Depois de Campinas/SP, a fila avança por outros polos de tecnologia do Brasil e revarre cidades periodicamente. Empresa nova entra na fila; empresa já contatada não recebe outra candidatura.

## Guardrails

- um envio bem-sucedido por empresa;
- somente endereços corporativos públicos do domínio oficial;
- prioridade para RH, recrutamento, talentos, jobs e careers;
- `contato@` só é elegível quando existe sinal de carreira/vaga no site;
- rejeita `noreply`, `abuse`, `privacy`, `dpo` e endereços inadequados;
- limite diário de envio;
- janela de horário e dias úteis;
- intervalo aleatório entre mensagens;
- `DRY_RUN=true` por padrão;
- CV e segredos nunca entram no Git.

## Início rápido

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
python -m dev_find init-db
python -m dev_find scan --city Campinas --state SP
python -m dev_find status
python -m dev_find daemon
```

Para envio real configure SMTP, defina `CV_PATH` para um PDF existente na VM e altere `DRY_RUN=false`.

## Busca

O provider recomendado é Brave Search via `BRAVE_SEARCH_API_KEY`. Sem chave, o sistema usa DDGS como fallback. A busca não presume que exista uma lista perfeita de “todas” as empresas: usa múltiplas consultas, deduplica por domínio e revarre cada cidade para incorporar empresas novas.

## Operação na VM

Arquivos de systemd estão em `deploy/`. O banco SQLite deve ficar fora do checkout em um diretório persistente, por exemplo `/var/lib/dev-find/dev-find.db`.

## Comandos

```bash
python -m dev_find init-db
python -m dev_find scan --city Campinas --state SP
python -m dev_find send-once
python -m dev_find daemon
python -m dev_find status
python -m dev_find add-city "São Carlos" SP
```

## Segurança

Não coloque senha SMTP, CV, banco SQLite ou arquivos `.env` no repositório. Use App Password/OAuth ou uma conta dedicada para envio. Respeite termos dos provedores de busca e dos sites visitados.
