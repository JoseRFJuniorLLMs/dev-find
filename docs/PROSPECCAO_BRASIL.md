# Prospecção nacional de empresas de TI

O dev-find pesquisa automaticamente municípios do Brasil via IBGE (CITIES_SCOPE=BR), além dos polos já priorizados em config/cities.csv. Também pode importar estabelecimentos da Receita Federal com CNAEs de desenvolvimento de software, consultoria, infraestrutura e serviços de TI.

A base CNPJ identifica **empresas**, não endereços de candidatura. O agente procura o site da empresa e só inclui caixas públicas institucionais que atendam às regras do crawler. Não infere e-mails nem contorna login ou bloqueios de sites.

## Operação

```bash
python -m dev_find import-cities --all-states
python -m dev_find sync-cnpj
python -m dev_find status
python -m dev_find export-catalog --output /var/lib/dev-find/contatos-validados.csv
```

A importação mensal da Receita é grande e deve ser executada com espaço em disco suficiente e supervisão. A seleção dos CNAEs não cobre necessariamente todas as empresas de TI e pode incluir atividades adjacentes. O fluxo automático de descoberta pode levar bastante tempo para percorrer toda a base.

O envio mantém `DRY_RUN=true` por padrão. Antes de habilitar SMTP, revise as fontes, a identidade do remetente, a mensagem e a base jurídica aplicável. Para envios maiores, use serviço profissional de email transacional/campanhas com supressão de opt-out, bounce, rate-limit e rastreabilidade; evite disparos indiscriminados. A publicação de um endereço na web não significa autorização para qualquer campanha.

Nenhuma alteração de produção é feita pelo importador. A publicação de código na VM exige pipeline de deploy e credenciais previamente configuradas.
