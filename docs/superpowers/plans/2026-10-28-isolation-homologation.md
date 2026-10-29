# Homologação de voicemail e gravações

**Objetivo:** executar os aceites viáveis das issues #88, #30 e #92 em
Asterisk descartável, com mídia e credenciais sintéticas; separar evidência
de laboratório dos requisitos externos de produção.

**Arquitetura:** ampliar o runner existente com modos explícitos de
autenticação voicemail e gravações. Reutilizar o dialplan gerado, SRTP,
CDR, reconciliador, catálogo e Handler HTTP do produto. Não alterar as
regras de autorização para facilitar testes.

**Execução solicitada:** tentar todas as provas possíveis, corrigir causas
verificadas, preservar relatórios sanitizados e revisão independente.

- [ ] Voicemail: negociar DTMF/SRTP; PIN correto e incorreto; t1/t10;
  três tentativas e encerramento; reprodução de marcador próprio e ausência
  de marcador estrangeiro. PINs, logs privados e áudio nunca entram no Git.
- [ ] Gravações: chamadas reais de ramais gerados; MixMonitor, WAV válido,
  CDR inequívoco; catálogo revisável e HTTP com papéis, negativa cruzada,
  revogação e origem proibida.
- [ ] Integrar os modos no runner e CI, exigindo todos os checks e cleanup.
- [ ] Rodar regressões e laboratório no mesmo commit; revisar implementação
  e evidências antes de registrar qualquer marco como concluído.
- [ ] Relatar os requisitos que dependem de SSO/identidade externa,
  infraestrutura alvo, proxy/certificados reais e aceite operacional.

**Riscos a verificar:** falso positivo por prompt de outro canal; confusão
t1/t10; PIN em log verboso; CDR/arquivo ambiguamente classificados;
negativa por política inteira quebrada; ausência de limpeza do container.

**Limites:** nenhuma implantação em cliente ou GO automático. Uma prova
unitária não substitui execução real; uma prova local não substitui aceite
da infraestrutura alvo.
