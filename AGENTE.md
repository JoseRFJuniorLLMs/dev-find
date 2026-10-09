# AGENTE.md — dev-find

## Missão

O **dev-find** é um agente Python de prospecção profissional contínua. Ele roda em uma VM, descobre empresas de tecnologia por cidade, identifica canais corporativos públicos de recrutamento, envia uma candidatura com CV e registra tudo em SQLite para não repetir empresas já contatadas.

A prioridade inicial é **Campinas/SP**. Depois, o agente percorre os polos configurados em `config/cities.csv` e volta periodicamente às cidades já pesquisadas para descobrir empresas novas.

## Regras obrigatórias

1. Nunca enviar mais de uma candidatura bem-sucedida para a mesma empresa.
2. Deduplicar empresas por domínio e candidaturas por `company_id`.
3. Priorizar e-mails corporativos públicos do domínio oficial: `rh@`, `recrutamento@`, `vagas@`, `jobs@`, `careers@`, `carreiras@`, `talentos@` e `people@`.
4. `contato@` só é elegível quando o site também apresenta sinal de carreira ou vagas.
5. Não usar e-mail pessoal de funcionário encontrado no site.
6. Rejeitar `noreply@`, `privacy@`, `dpo@`, `abuse@`, `security@` e equivalentes.
7. Respeitar `robots.txt`, limite diário, janela de envio e intervalo entre mensagens.
8. `DRY_RUN=true` é o padrão. Não habilitar envio real sem validar SMTP, remetente e CV.
9. Nunca colocar CV, credenciais, banco SQLite ou `.env` no Git.
10. O repositório é público. Segredos ficam fora do checkout.

## Arquitetura

```text
config/cities.csv
      |
      v
SearchDiscovery
Brave Search / DDGS
      |
      v
empresa + domínio oficial
      |
      v
WebsiteCrawler
carreiras / vagas / contato
      |
      v
ranking de e-mail corporativo
      |
      v
SQLite
companies / contacts / applications
      |
      v
Mailer SMTP + CV
      |
      v
status=sent -> empresa não volta para a fila
```

## Estrutura

```text
src/dev_find/
  app.py         orquestra scan + envio + loop
  cli.py         comandos CLI
  config.py      configuração via ambiente
  crawler.py     site oficial + e-mails
  db.py          SQLite + deduplicação
  discovery.py   busca de empresas por cidade
  emailer.py     SMTP + anexo do CV

config/cities.csv
templates/application.txt
deploy/dev-find.service
deploy/install.sh
```

## Requisitos da VM

- Linux com systemd;
- Python 3.11+;
- Git;
- saída HTTPS;
- saída SMTP;
- diretório persistente para SQLite.

Diretórios esperados:

```text
/opt/dev-find/                 checkout Git
/opt/dev-find-private/         CV e arquivos privados
/var/lib/dev-find/             banco SQLite
/etc/dev-find.env              configuração e segredos
```

## Deploy inicial

### 1. Clonar

```bash
sudo git clone https://github.com/JoseRFJuniorLLMs/dev-find.git /opt/dev-find
cd /opt/dev-find
```

### 2. Instalar

```bash
sudo bash deploy/install.sh
```

O instalador cria o usuário `devfind`, os diretórios persistentes, a virtualenv, instala o pacote, prepara `/etc/dev-find.env` e registra o serviço systemd.

### 3. Instalar o CV

O CV fica fora do Git:

```bash
sudo cp /caminho/do/curriculo.pdf /opt/dev-find-private/cv.pdf
sudo chown devfind:devfind /opt/dev-find-private/cv.pdf
sudo chmod 600 /opt/dev-find-private/cv.pdf
```

No ambiente:

```text
CV_PATH=/opt/dev-find-private/cv.pdf
```

### 4. Configurar ambiente

```bash
sudo nano /etc/dev-find.env
```

Campos principais:

```text
DRY_RUN=true

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_STARTTLS=true
FROM_EMAIL=
FROM_NAME=

APPLICANT_NAME=José Ribamar Ferreira Junior
APPLICANT_ROLE=Engenheiro de IA e Dados
APPLICANT_EMAIL=
APPLICANT_PHONE=

LINKEDIN_URL=https://www.linkedin.com/in/joserfjunior/
GITHUB_URL=https://github.com/JoseRFJuniorLLMs
CV_PATH=/opt/dev-find-private/cv.pdf
```

Para Gmail, usar credencial de aplicativo/OAuth adequada. Nunca versionar senha.

## Validação antes de enviar

Sempre testar primeiro em dry-run:

```bash
cd /opt/dev-find
sudo -u devfind .venv/bin/python -m dev_find init-db
sudo -u devfind .venv/bin/python -m dev_find scan --city Campinas --state SP
sudo -u devfind .venv/bin/python -m dev_find status
sudo -u devfind .venv/bin/python -m dev_find send-once
```

Com `DRY_RUN=true`, `send-once` apenas mostra o próximo destinatário elegível.

## Ativar envio real

Após revisar os destinatários e validar SMTP/CV:

```text
DRY_RUN=false
```

Depois:

```bash
sudo systemctl restart dev-find
sudo systemctl status dev-find
```

## Logs

```bash
journalctl -u dev-find -f
journalctl -u dev-find --since today
```

## Atualização

```bash
cd /opt/dev-find
sudo systemctl stop dev-find
sudo git pull --ff-only origin main
sudo .venv/bin/pip install -e .
sudo -u devfind .venv/bin/python -m pytest -q
sudo systemctl start dev-find
sudo systemctl status dev-find
```

## Banco e deduplicação

Banco padrão:

```text
/var/lib/dev-find/dev-find.db
```

Garantias principais:

- `companies.domain UNIQUE`;
- `applications.company_id UNIQUE`;
- candidatura com `status='sent'` não volta à fila;
- falha temporária pode ser retentada até `MAX_SEND_ATTEMPTS`;
- reiniciar a VM não perde histórico.

## Backup

Para backup simples:

```bash
sudo systemctl stop dev-find
sudo mkdir -p /var/backups
sudo cp /var/lib/dev-find/dev-find.db /var/backups/dev-find.db
sudo systemctl start dev-find
```

Para ambiente contínuo, preferir a API de backup do SQLite ou `.backup` via `sqlite3`.

## Expansão geográfica

As cidades ficam em:

```text
config/cities.csv
```

Campinas começa com prioridade máxima. As cidades são reprocessadas após `CITY_RESCAN_DAYS`.

Adicionar cidade:

```bash
sudo -u devfind /opt/dev-find/.venv/bin/python -m dev_find add-city "Nova Cidade" SP --priority 70
```

## Limites iniciais recomendados

```text
MAX_EMAILS_PER_DAY=8
MIN_SEND_INTERVAL_SECONDS=1200
MAX_SEND_JITTER_SECONDS=1800
SEND_WINDOW_START=08:30
SEND_WINDOW_END=17:30
SEND_WEEKDAYS=0,1,2,3,4
```

Aumentar volume apenas depois de acompanhar entregabilidade e respostas.

## Health operacional

Validar periodicamente:

1. `systemctl status dev-find`;
2. logs sem loop de erro;
3. SQLite gravável;
4. CV legível por `devfind`;
5. DNS/HTTPS funcionando;
6. SMTP autenticando;
7. `DRY_RUN` no estado esperado;
8. CI do GitHub verde.

## CI

Workflow:

```text
.github/workflows/ci.yml
```

O CI usa Python 3.12, instala `.[dev]` e roda `pytest -q`.

Qualquer mudança em deduplicação, crawler ou envio deve manter testes de:

- domínio duplicado;
- contato duplicado;
- empresa já enviada não volta;
- e-mail pessoal/sensível rejeitado;
- contato genérico exige sinal de carreira.

## Critério de pronto

O agente está corretamente implantado quando:

- systemd está ativo;
- Campinas pode ser pesquisada;
- empresas e contatos entram no SQLite;
- dry-run mostra um candidato elegível;
- envio real anexa o CV;
- empresa enviada nunca reaparece;
- reboot não apaga histórico;
- revarredura encontra empresas novas;
- nenhum segredo ou CV foi publicado no Git.
