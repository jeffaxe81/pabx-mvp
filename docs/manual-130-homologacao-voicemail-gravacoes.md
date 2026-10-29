# Manual 130 — Homologação de autenticação voicemail e gravações

## Execução descartável

```bash
python3 -m pip install -r lab/requirements.txt
python3 -m lab.asterisk_lab --calls --voicemail-auth --report lab-results/voicemail-auth.json
python3 -m lab.asterisk_lab --calls --recordings --report lab-results/recordings.json
python3 -m lab.asterisk_lab --calls --recordings --voicemail-auth --report lab-results/access-homologation.json
```

Requer Linux, Docker, Git e OpenSSL. O runner exporta a configuração do
commit, gera credenciais e mensagens sintéticas em staging privado, usa
somente loopback e remove o container próprio ao terminar. Não executar
paralelamente dois runners que disputem as portas SIP do laboratório.

## Voicemail

O cliente negocia TLS, SDES-SRTP e RFC4733. O ensaio usa as rotas `*97`
do produto, o PIN correto e três tentativas com o PIN da outra empresa,
nas duas direções t1/t10. O aceite exige estado autenticado, reprodução
da mensagem própria com marcador de áudio recebido e autenticado,
ausência de marcador estrangeiro, negativa do PIN estrangeiro, BYE após
o limite de tentativas e canais limpos.

Mensagens verbosas do Asterisk podem conter PINs incorretos. O arquivo
verboso fica privado no container; o relatório só publica indicadores
sanitizados, contagens e o SHA. Não publicar logs brutos, PINs, SDP,
credenciais, mensagens ou áudio do staging.

O limite comprovado é de três tentativas por chamada. Isso não equivale
a bloqueio persistente entre chamadas nem demonstra ACLs de filesystem
distintas para empresas atendidas pelo mesmo processo Asterisk.

## Gravações

Quatro empresas (t1/t2/t3/t10) iniciam chamadas sintéticas 1101 → 1102
no mesmo segundo. Cada empresa transmite um marcador diferente. O aceite
exige arquivos diferentes, WAV válido com marcador próprio e sem marcadores
estrangeiros, CDR inequívoco, catálogo aplicado no staging, acesso do agente
proprietário/supervisor/admin e negativas para outro agente/empresa,
credencial ausente, origem proibida e credencial revogada.

O catálogo usa o reconciliador e a API HTTP do produto. A importação
automática neste ensaio é limitada a arquivos e evidências sintéticos no
staging descartável; o fluxo de produção continua exigindo revisão.

## Nomes sem colisão e compatibilidade

Rotas explícitas MixMonitor incluem tenant literal e `${UNIQUEID}`, com
caller reduzido a dígitos via `FILTER`. Arquivos de ramais gerenciados
usam `AAAAMMDD-HHMMSS-caller-tN-destino-uniqueid.wav`. O reconciliador
exige concordância do ID único, tenant, horário, caller e destino com o
mesmo CDR. Identidade repetida ou contraditória é recusada.

Arquivos legados continuam legíveis e só geram propostas quando a
correlação antiga for inequívoca. Nenhum arquivo é renomeado nem recebe
autorização apenas por conter um tenant no nome.

## Gates e limites

Os modos só aprovam quando todos os checks requeridos estiverem presentes
e verdadeiros. Código do laboratório e módulos de produto importados
precisam estar limpos no Git; alterações staged/untracked na queue-api
invalidam a atribuição da evidência ao commit.

O job `access-homologation` preserva o JSON sanitizado mesmo em falhas.
Um resultado local ou de CI deve ser conferido no SHA correspondente.
O plano de 16 semanas só muda após revisão do aceite completo; estes
comandos não autorizam produção.

Identidade/SSO, rede/certificados/proxy reais, infraestrutura do cliente,
retenção/backup e aceite operacional permanecem provas separadas. Não
fechar as issues #30/#88/#92 apenas porque os testes unitários passaram.
