# Manual 65 — Rodando o projeto a partir do Windows via WSL2 (item #65)

## Por que isso é necessário
Três serviços deste projeto (`asterisk`, `queue-api`, `admin-api`)
usam `network_mode: host` no `docker-compose.yml` — necessário pro
SIP/RTP do Asterisk funcionar sem dor de cabeça com NAT, e pra
`queue-api`/`admin-api` enxergarem o AMI em `127.0.0.1:5038`.

**Host networking é um recurso do kernel Linux.** O Docker Desktop
pra Windows roda os containers dentro de uma VM Linux (via WSL2 ou
Hyper-V) e faz ponte de rede entre essa VM e o Windows — nesse
cenário, `network_mode: host` aponta pra dentro da VM do Docker, não
pro Windows em si. O resultado prático: `127.0.0.1:5038` não
funcionaria como esperado, e o próprio SIP/RTP (a razão de existir
desse modo de rede aqui) ficaria comprometido.

**A solução não é contornar isso dentro do Docker Desktop — é rodar
o Docker de um jeito que faça host networking significar algo real.**

## O caminho recomendado: Docker Engine nativo dentro do WSL2
Não o Docker Desktop tradicional (que "empresta" rede do Windows pra
uma VM) — o **Docker Engine instalado direto dentro de uma distro
Linux do WSL2**, do mesmo jeito que seria instalado num servidor
Ubuntu de verdade. Nesse caso, `network_mode: host` funciona porque
o "host" É o Linux do WSL2, não uma camada extra de tradução.

### Passo a passo
1. **Instale o WSL2** (se ainda não tiver), com uma distro Ubuntu:
   ```powershell
   wsl --install -d Ubuntu
   ```
   (Requer reiniciar o Windows na primeira vez, se for instalação nova)

2. **Abra o Ubuntu do WSL2** (menu Iniciar → Ubuntu, ou `wsl` no
   PowerShell) e instale o Docker Engine seguindo a documentação
   oficial pra Ubuntu (não o Docker Desktop):
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker $USER
   ```
   Feche e reabra o terminal do WSL2 depois do `usermod` (o grupo
   novo só é aplicado numa sessão nova).

3. **Confirme que o Docker está rodando de verdade dentro do WSL2**
   (não é o daemon do Docker Desktop sendo compartilhado):
   ```bash
   docker info | grep "Operating System"
   ```
   Deveria mostrar algo como `Ubuntu` — se mostrar
   `Docker Desktop`, o WSL2 ainda está usando o daemon do Windows, e
   os passos acima precisam ser revistos (geralmente significa que o
   Docker Desktop está com a integração WSL2 ligada nas configurações
   — desligue "Use the WSL 2 based engine" nas configurações do
   Docker Desktop, ou desinstale o Docker Desktop e reinstale o
   Docker Engine seguindo o passo 2 de novo)

4. **Clone o projeto de dentro do WSL2** (não do lado Windows, ex:
   não em `/mnt/c/Users/...`) — sistemas de arquivo montados do
   Windows têm desempenho bem pior pra I/O intenso, e este projeto
   grava configuração e áudio com frequência:
   ```bash
   cd ~
   git clone https://github.com/jeffaxe81/pabx-mvp.git
   cd pabx-mvp
   ```

5. **Rode o gerador de segredos** (manual 50) e siga o roteiro de
   implantação normalmente (manual 00) — a partir daqui, é
   exatamente igual a rodar num servidor Ubuntu de verdade:
   ```bash
   python3 scripts/generate_secrets.py
   docker compose up -d
   ```

6. **Acesse os painéis do lado Windows normalmente** — o WSL2 expõe
   `localhost` do Windows pras portas do Linux automaticamente
   (comportamento padrão do WSL2, sem configuração extra):
   `http://localhost:8091` (admin), `http://localhost:8082/painel-operacional.html`
   (operacional)

## Alternativas, se WSL2 não for viável
- **VM Linux completa** (VirtualBox/Hyper-V/VMware, Ubuntu/Debian) —
  mais isolado, sem nenhuma sutileza de como o WSL2 lida com rede,
  ao custo de precisar gerenciar uma VM separada
- **Servidor Linux remoto/nuvem** (VPS) — mais parecido com onde isso
  rodaria de verdade em produção; exige cuidado extra com firewall e
  senhas antes de expor qualquer porta publicamente (ver manual 50)

## Como testar
1. Siga os passos acima até `docker compose up -d`
2. `docker compose ps` — confirme que todos os serviços estão `Up`
3. Registre um softphone num ramal (manual 01) — se conseguir
   registrar e ligar, a rede está funcionando de verdade

## Limitações conhecidas (honestidade técnica)
- **Nunca testado de fato num Windows real** — este manual foi
  escrito com base no comportamento documentado/conhecido do
  WSL2/Docker, não confirmado rodando neste ambiente (que é Linux,
  não Windows)
- **Docker Desktop com integração WSL2 ligada pode causar confusão**
  — se o Docker Desktop estiver instalado e com "Use the WSL 2 based
  engine" ativo nas configurações, o comando `docker` dentro do WSL2
  pode estar na verdade se comunicando com o daemon do Docker
  Desktop (que tem a mesma limitação de rede) em vez do Docker Engine
  nativo — o passo 3 acima existe justamente pra pegar essa confusão
- **Hyper-V/virtualização precisa estar habilitada na BIOS/Windows**
  pra WSL2 funcionar — fora do escopo deste manual, é um pré-requisito
  do próprio WSL2, não deste projeto
