# AXE PABX — 30 entregas: proteção do provisionamento de ramais dinâmicos

**Data:** 30/10/2026. **Status:** `CODE_REGISTERED_PENDING_REAL_HOMOLOGATION`.

## Objetivo

Endurecer a geração dos arquivos Asterisk para ramais dinâmicos administrados pelo painel. O método `render_all` em `admin-api/conf_generator.py` agora executa trinta verificações independentes em `dynamic_extension_invariants.py`, **depois de validar o cadastro persistido e antes de retornar os arquivos para publicação e recarga AMI**.

**As 30 entregas são controles de integridade e proteção de um subsistema real, não 30 novos produtos ou trinta testes SIP de produção.** Complementam o gate de **20 controles de provisionamento do tenant** da PR #189; este novo lote trata especificamente do provisionamento dos **ramais** dentro das empresas.

## 30 controles integrados

| Nº | Área de especialidade | Controle |
|---:|---|---|
| DE-01 | Multiempresa | Validade de todos os tenant IDs |
| DE-02 | PJSIP | Unicidade de nomes de endpoints dinâmicos |
| DE-03 | Discagem | Unicidade do número dentro de cada tenant |
| DE-04 | Implantação | Quantidade total de arquivos gerados correta |
| DE-05 | Implantação | Nomes de arquivos exatos, sem arquivos desconhecidos |
| DE-06 | Segurança | Cada arquivo gerado é texto |
| DE-07 | Segurança | Ausência de caracteres NUL/CR nos arquivos |
| DE-08 | Resiliência | Limite de tamanho de 2 MiB por arquivo |
| DE-09 | Governança | Cabeçalho de arquivo gerado pelo painel presente |
| DE-10 | PJSIP | Endpoint dinâmico esperado existe uma só vez |
| DE-11 | PJSIP | Nenhum endpoint inesperado na configuração |
| DE-12 | Multiempresa | Contexto interno do endpoint corresponde ao tenant |
| DE-13 | BLF | Contexto de assinatura corresponde ao tenant |
| DE-14 | PJSIP | Referência de autenticação do endpoint é correta |
| DE-15 | PJSIP | Referência ao AOR do endpoint é correta |
| DE-16 | BINA | CallerID da configuração confere com cadastro |
| DE-17 | Voicemail | Mailbox do endpoint corresponde à empresa |
| DE-18 | PJSIP | Bloco dedicado de autenticação existe uma vez |
| DE-19 | PJSIP | Username SIP correto |
| DE-20 | Segurança SIP | Segredo SIP corresponde ao cadastro |
| DE-21 | PJSIP | Bloco AOR correspondente existe |
| DE-22 | Registro SIP | Limite de um contato por AOR |
| DE-23 | Registro SIP | Política de substituição de contato antigo |
| DE-24 | Discagem | Ramais apresentados no dialplan correspondem à lista esperada |
| DE-25 | Gravação | MixMonitor presente no dialplan do ramal |
| DE-26 | CDR | Accountcode da chamada atribuído à empresa correta |
| DE-27 | Discagem | Destino PJSIP do ramal corresponde ao endpoint |
| DE-28 | Discagem | Encerramento de fluxo com Hangup |
| DE-29 | BLF | Hints por tenant correspondem exatamente aos ramais |
| DE-30 | Voicemail | Caixas dinâmicas conferem nome, PIN, identificação e e-mail |

## Alterações concretas

- Novo `admin-api/dynamic_extension_invariants.py` com 30 verificações estruturais de saída.
- `admin-api/conf_generator.py` passa a recusar a publicação quando qualquer regra falha. Falhas retornam **somente IDs DE-xx**, sem expor credenciais ou dados de clientes.
- Novo `admin-api/tests/test_dynamic_extension_invariants.py` com cenários reais de `render_all`, alterações adversariais em `.conf`, isolamento `t1`/`t10`, ausência de arquivos e proteção contra vazamento de PIN/segredos nos erros.
- O mecanismo atua apenas na criação/edição de ramais já suportada pelo admin-api, sem alterar dialplan estático, áudio, mídia ou fluxo de chamadas.

## Limites e aceitação

Estas verificações são **estáticas**; não comprovam que Asterisk aceitou a configuração, que o ramal registrou por TLS, que os codecs negociaram SRTP nem que MixMonitor produziu áudio válido. A lógica de publicação e rollback existente continua responsável por persistência e recarga.

A PR somente deve ser integrada após todos os testes da CI em verde. **Nenhuma homologação do PABX de cliente foi realizada**, as 15 provas operacionais continuam diferidas (#173) e o progresso formal continua em **7/16 marcos (43,8%)**. Sem autorização de produção.
