# Manual 28 — Alta disponibilidade e backup (item #33)

## Leia isto primeiro: o que este item **não** é
O documento de funcionalidades original pedia "alta disponibilidade e
backup: backup automático, servidor reserva, recuperação rápida em
caso de falha". Sendo direto: **este projeto não implementa alta
disponibilidade de verdade** (failover automático pra um servidor
reserva). Isso exigiria uma segunda instância de Asterisk sincronizada
em tempo real (via replicação de estado, um load balancer de SIP na
frente, etc.) — uma mudança de arquitetura muito maior do que cabe
numa única entrega, e que só faz sentido com hardware/infraestrutura
redundante de verdade por trás.

**O que este item entrega**: backup automático de configuração e
dados de negócio, com um procedimento de restauração documentado e
testável. Isso reduz o tempo de recuperação depois de uma falha (você
não perde configuração nem histórico), mas não elimina o container
único do Asterisk como ponto único de falha.

## O que é feito backup
Um novo serviço `backup` no `docker-compose.yml` roda uma vez por dia,
empacotando num `.tar.gz`:
- `asterisk/` (toda a configuração, incluindo os ramais gerados
  dinamicamente pelo painel)
- `admin/` e `webphone/` (as interfaces)
- `provisioning/` (cadastro de dispositivos)
- `recordings/` (gravações de chamada)
- `docker-compose.yml` e `prompt-base-pabx.md`
- Os dois **volumes Docker nomeados**: `admin_data` (usuários do
  painel, ramais cadastrados) e `queue_api_data` (histórico de
  relatórios)

## Por que o container de backup não usa o socket do Docker
Uma forma comum de fazer backup de volumes Docker é dar ao container
de backup acesso ao `/var/run/docker.sock` e deixar ele rodar
`docker run`/`docker cp` pra manipular outros containers/volumes. **De
propósito, não fiz isso aqui** — montar o socket do Docker num
container equivale, na prática, a dar acesso root ao host inteiro (um
container com esse acesso pode criar outros containers privilegiados,
ler qualquer arquivo do host, etc.). Pra um serviço de backup, esse
risco não vale o benefício.

Em vez disso, os dois volumes nomeados são **montados diretamente**
(como qualquer outro volume) no container de backup, só que como
somente leitura (`:ro`). Isso cobre o backup perfeitamente. A única
consequência é que a **restauração** desses dois volumes específicos
precisa de um passo manual (ver abaixo) em vez de ser 100% automática
— uma troca deliberada de conveniência por segurança.

## Como configurar
```yaml
BACKUP_RETENTION_DAYS: "0"   # 0 = nunca apaga backup antigo sozinho
```
Retenção desligada por padrão, mesmo padrão de segurança do resto do
projeto — apagar backup automaticamente é uma ação com efeito colateral
real. Defina um número de dias (ex: `"30"`) pra ativar o expurgo.

## Como restaurar
1. `docker compose down`
2. `sh backup/restore.sh backups/pabx-backup-AAAAMMDD-HHMMSS.tar.gz`
   (rodar **no host**, não dentro de um container)
3. O script pede confirmação, restaura os arquivos de configuração, e
   **imprime na tela os dois comandos `docker run`** necessários pra
   restaurar os volumes nomeados (usuários do painel e histórico de
   relatórios) — copie e rode esses comandos
4. `docker compose up -d`

## Como testar manualmente
1. `docker compose up -d`
2. Espere o container `pabx-backup` rodar pelo menos uma vez (ou force
   manualmente: `docker exec pabx-backup sh /pabx-scripts/backup.sh`)
3. Confirme que apareceu um arquivo em `./backups/pabx-backup-*.tar.gz`
4. Crie um ramal pelo painel de administração, faça uma chamada
   (gerando histórico), depois rode o backup de novo
5. Simule uma perda: `docker compose down -v` (isso apaga os volumes
   nomeados de propósito, só pra teste)
6. `docker compose up -d` de novo (recria tudo vazio)
7. Rode `backup/restore.sh` com o backup do passo 4, seguindo as
   instruções que ele imprime na tela
8. Confirme que o ramal criado e o histórico voltaram

## Teste automatizado
- `backup/tests/test_retention.py` — expurgo desligado por padrão,
  respeita o prazo configurado, ignora arquivo que não é backup
- `tests/test_backup_scripts.py` — os scripts existem e são
  executáveis, `backup.sh` arquiva antes de rodar a retenção,
  `restore.sh` exige confirmação explícita e documenta o passo manual
  dos volumes
- `tests/test_docker_compose.py` — serviço de backup presente, **sem**
  o socket do Docker montado, os dois volumes nomeados montados como
  somente leitura, retenção desligada por padrão

## Limitações conhecidas (honestidade técnica)
- **Não é alta disponibilidade** (ver aviso no topo) — é backup +
  restauração mais rápida, não failover automático
- **`backup.sh`/`restore.sh` não têm teste de integração real** — a
  mesma situação já documentada pro resto dos scripts de
  infraestrutura deste projeto (mail_relay.py, os clientes AMI): só
  dá pra validar de fato rodando o ambiente Docker completo
- **Restauração dos volumes nomeados é manual** (decisão deliberada
  de segurança, ver seção acima) — não é "um comando só"
- **Backup roda uma vez por dia, sem horário configurável** — não dá
  pra escolher "sempre de madrugada", é a cada 24h a partir de quando
  o container subiu
- **Sem backup fora do servidor** (offsite) — os backups ficam na
  pasta `./backups/` do próprio host; se o disco falhar, o backup
  falha junto. Copiar `./backups/` pra outro lugar (outro servidor,
  armazenamento em nuvem) é responsabilidade de quem opera, fora do
  escopo deste projeto
- **Sem teste automático de restauração** — o passo 5-8 do teste
  manual acima precisa ser feito por uma pessoa; não há verificação
  automática de que um backup realmente restaura com sucesso
