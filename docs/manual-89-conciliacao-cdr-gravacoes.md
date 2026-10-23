# Manual 89 — Conciliação CDR com propostas de gravações por tenant

## Objetivo e escopo

Reduzir trabalho manual de identificação **sem conceder acesso automaticamente**.
O utilitário `queue-api/recording_cdr_candidates.py` examina áudios e
eventos **originais** `Cdr` do Asterisk AMI, e só produz propostas
de manifesto JSONL quando os dados se corroboram.

A proposta somente é produzida quando *todos* os campos seguintes
concordam com o arquivo: `AccountCode=tN`, 
`DestinationContext=tN-internal`, `DestinationChannel=PJSIP/tN-...`,
`Disposition=ANSWERED`, `UniqueID`, `CallerIDNum`,
`Destination` e `StartTime`. Dois eventos elegíveis para a
mesma gravação tornam a associação **ambígua**, mesmo quando
de um único tenant. Arquivos com nome inesperado ou links simbólicos
não são importados.

Essa correlação não é prova criptográfica. Exige origem genuína
dos eventos AMI, controle de acesso ao diretório e verificação humana
do vínculo; não equivale à identidade verificada do usuário.

## Novo accountcode nos dialplans

O código passa a escrever `CDR(accountcode)=t1` ou `t2` nos
caminhos estáticos de gravação e filas, e `tN` nas configurações
geradas para tenants novos e ramais administrados.

**Só novos CDRs após a aplicação e recarga correta da configuração
poderão conter essa marcação.** Não preencher automaticamente
`AccountCode` faltante nos registros antigos. Eventos de
fila, pickup e gravações com nomes que não seguem o formato esperado
permanecem sem proposta; há risco de múltiplos CDRs por chamada.

## Execução local, sem tocar produção

Primeiro exporte eventos JSONL de uma captura AMI **autorizada**.
O arquivo `call_log.jsonl` do relatório agregado **não serve**:
ele não contém todos os campos originais nem o `UniqueID`.

```bash
python3 queue-api/recording_cdr_candidates.py \
  --recordings-dir /var/lib/pabx/recordings \
  --cdr-jsonl /dados-privados/eventos-cdr-ami.jsonl \
  --output /dados-privados/candidatos-gravacoes.jsonl
```

A saída é um arquivo novo, com permissões `0600`; nunca sobrescreve
outro manifesto nem altera o catálogo. Somente o resumo das quantidades
é impresso, sem dados de chamada. Se não existir nenhuma proposta,
o arquivo estará vazio. O limite de entrada é 4 MiB ou 10 mil eventos.

Depois de conferir evidências no CDR e na mídia:

```bash
python3 queue-api/recording_catalog.py \
  --policy /dados-privados/recording_access.json \
  --recordings-dir /var/lib/pabx/recordings \
  --manifest /dados-privados/candidatos-gravacoes.jsonl
# --apply só após validação da associação; ver Manual 83.
```

Nenhuma gravação será listada ou reproduzida por usuário até a etapa
de catalogação ter sido explicitamente aprovada e aplicada.

## Testes e pontos pendentes

- Testes negativos de `AccountCode`, contexto, canal, timestamp,
  chamador, destino e `UniqueID`.
- Rejeição de CDR duplicado ou conflitante entre tenants.
- Testes de diretório, links simbólicos, nome inesperado,
  destino protegido, geração estática e templates t3+.

Pendente para **GO**: validação de CDR real na versão implantada
do Asterisk, conferência de formatos de MixMonitor em cada fluxo
(incluindo filas e pickup), autenticação federada dos usuários,
regras de retenção/backup, proxy HTTPS, homologação de SIP/RTP e
prova de isolamento entre tenants.

Não rodar sobre o ambiente de produção sem homologação do dialplan
e janela de mudança com rollback.
