# Marco 8 — Inspeção inequívoca do canal de voicemail

A evidência em Asterisk descartável para `*97` só pode ser marcada
como verdadeira quando a mesma linha de `core show channels concise`
comprova:

- canal PJSIP com sufixo hexadecimal ligado ao endpoint SIP esperado;
- `Context` exatamente `tN-internal`;
- `Exten` exatamente `*97`;
- aplicação `VoiceMailMain` com a mailbox `endpoint@tN` exata;
- uma única linha correspondente, sem somar atributos de canais distintos.

Nomes `t1` e `t10` não são equivalentes, tampouco `t1-1001`
e `t1-10010`. Valores inválidos e canais duplicados falham fechado.

Essa verificação **não** introduz nem comprova autenticação de PIN ou
isolamento físico de mensagens. A issue #88 e o marco 8 permanecem
abertos até os cenários de PIN correto/errado e cross-tenant reais,
além dos requisitos de gravações.
