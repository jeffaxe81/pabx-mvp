# Manual 00 — Roteiro de implantação (primeiros passos em servidor real)

Este projeto tem 37 manuais e 8 serviços Docker. Ativar tudo de uma
vez seria um jeito garantido de não saber onde procurar quando algo
não funcionar. Este roteiro define uma **ordem de validação**: cada
fase só faz sentido depois que a anterior está funcionando de
verdade, não só "configurada".

## Antes de começar
- Servidor Linux com Docker e Docker Compose instalados — se sua
  máquina é Windows, veja `docs/manual-65-windows-wsl2.md` **antes**
  de continuar (o projeto usa `network_mode: host`, que não funciona
  como esperado no Docker Desktop pra Windows)
- Portas livres: 5060/UDP, 5061/TCP, 8089/TCP (SIP/WebRTC), 8080-8082
  (provisionamento/webphone), 8090/8091/8092 (APIs)
- Pelo menos 2 softphones ou ramais físicos pra testar chamadas de
  verdade (um sozinho não testa transferência, fila, grupo de toque)
- Se for ativar a IA (fase 7): 8GB+ de RAM livre e paciência — o
  primeiro download do modelo Llama 3 tem vários GB

## Fase 1 — O PABX liga e faz uma chamada
**Objetivo**: provar que a base funciona antes de mexer em qualquer
funcionalidade avançada.

1. `git clone` o repositório, `cd` nele
2. **Gere segredos fortes de verdade** (obrigatório, não pule):
   `python3 scripts/generate_secrets.py` — as senhas do repositório
   são placeholders públicos, subir com elas é o mesmo que não ter
   senha nenhuma. Leia o aviso que o script imprime antes de comitar
   qualquer coisa de volta pro GitHub (ver `docs/manual-50-geracao-segredos.md`)
3. Gere os certificados TLS de verdade (os do repositório são
   self-signed de exemplo) — ver `docs/manual-02-criptografia.md`
4. `docker compose up -d asterisk`
5. Registre 2 softphones nos ramais `t1-1001` e `t1-1002`
   (`docs/manual-01-core-ramais.md`)
6. Ligue de um pro outro — se o áudio passa nos dois sentidos, a base
   está sólida
7. Rode `python3 scripts/verify_deployment.py` — confirma
   mecanicamente que os segredos foram trocados e que os serviços
   que você já subiu estão respondendo (não substitui o passo 6, só
   complementa — ver `docs/manual-51-verificacao-pos-deploy.md`)

**Não prossiga pra fase 2 até isso funcionar.** Qualquer problema de
rede, NAT, ou certificado vai se multiplicar em todas as outras
funcionalidades.

## Fase 2 — Telefonista e fila
1. `docker compose up -d queue-api webphone`
2. Registre o console da telefonista (`docs/manual-06-telefonista-web.md`)
3. Ligue de `t1-1001` pro ramal `1000` — confirme que toca no console
   web, atende, grava (`docs/manual-09-gravacao-chamadas.md`), e some
   da lista depois de desligar
4. Teste a fila de verdade com **duas telefonistas logadas ao mesmo
   tempo** (`docs/manual-14-multiplas-telefonistas.md`) — uma
   única telefonista não revela bug nenhum de fila

## Fase 3 — Painel de administração
1. Gere o hash da senha do primeiro admin, configure
   `ADMIN_PASSWORD_HASH`, suba `admin-api` e `admin`
2. Crie um ramal novo pelo painel (não editando `.conf` na mão) —
   confirme que ele registra de verdade
3. Crie um segundo usuário como **supervisor** e confirme que ele
   não consegue criar/editar ramal (nem pela interface, nem chamando
   a API diretamente — `docs/manual-25-permissoes-perfis.md`)
4. Ative o 2FA numa conta de teste antes de ativar na sua conta
   principal (`docs/manual-26-2fa.md`)

## Fase 4 — URA, regras de discagem, callback
Essa fase depende de um gateway TDM/tronco SIP de verdade pra testar
chamadas de entrada de fato — sem isso, use as extensões de teste
internas (`700` pra URA, `650` pro atendente virtual) discadas de um
ramal já registrado.

1. Grave os áudios reais da URA **antes de ir pra produção** — os que
   vêm no repositório são só *beeps* placeholder
   (`docs/manual-23-ura.md`, seção "leia isto")
2. Teste o menu completo: horário comercial, fora de horário, modo
   feriado, callback (opção 9)
3. Configure pelo menos um número de teste na lista de bloqueio e um
   cliente VIP, confirme que as duas regras têm o efeito esperado
   (`docs/manual-20-discagem-externa.md`, `docs/manual-33-transferencia-inteligente.md`)

## Fase 5 — Backup (faça isso antes de confiar dados reais ao sistema)
1. Suba o serviço `backup`, force uma execução manual
   (`docker exec pabx-backup sh /pabx-scripts/backup.sh`)
2. **Teste a restauração de verdade** — não assuma que funciona só
   porque o backup foi criado. Siga o procedimento completo do
   `docs/manual-28-backup-disponibilidade.md`, incluindo o passo
   manual dos volumes Docker
3. Só depois de restaurar com sucesso uma vez, confie o sistema com
   dados reais de clientes

## Fase 6 — Monitoramento e fraude
1. Configure o painel operacional, confirme que mostra fila,
   ramais e qualidade de chamada em tempo real
2. Ative os alertas de fraude com um limiar baixo só pra confirmar
   que o alerta dispara (depois suba o limiar pro valor real de
   produção) — `docs/manual-27-deteccao-fraude.md`

## Fase 7 — IA (só se for usar; é a parte menos testada do projeto)
**Leia os avisos de honestidade técnica no início de
`docs/manual-36-transcricao-resumo-sentimento.md` e
`docs/manual-37-atendente-virtual.md` antes de ativar isso em
produção** — essa é a única parte do sistema que nunca foi validada
contra os modelos de IA reais (Whisper/Llama 3) rodando de verdade.

1. Suba `ollama` e `ai-worker` com `AI_FEATURES_ENABLED=false` primeiro
   (o padrão) — confirme que a API responde normalmente mesmo sem
   processar nada
2. Baixe o modelo (`docker exec pabx-ollama ollama pull llama3`) -
   isso sozinho já testa se o hardware aguenta
3. Ative `AI_FEATURES_ENABLED=true` com **uma gravação de teste só**,
   confira o resultado antes de deixar processando tudo
4. Meça quanto tempo o processamento leva no seu hardware real antes
   de decidir se isso é viável em produção (pode ser lento demais em
   CPU modesta)

## Se algo não funcionar
Cada manual tem uma seção "Limitações conhecidas (honestidade
técnica)" — antes de assumir que é bug, confira se o comportamento
já está documentado ali como limitação esperada. Boa parte das
integrações de rede (AMI, SMTP, webhooks, Whisper/Ollama) nunca foram
testadas contra os sistemas reais neste projeto — são a primeira
coisa a suspeitar quando algo não bate com o esperado.
