# Manual 02 — Criptografia (TLS + SRTP)

## O que é
Sinalização SIP protegida por TLS (evita que alguém na rede leia quem
está ligando pra quem) e áudio protegido por SRTP (evita que alguém
grave a conversa capturando pacotes).

## Como configurar
- Certificado em `asterisk/certs/asterisk.crt` + `asterisk.key`
  (self-signed, gerado com `openssl req -x509 ...`; **trocar por um
  certificado válido em produção**, ex: Let's Encrypt)
- Transporte declarado em `asterisk/pjsip.conf`, seção
  `[transport-tls]`, escutando na porta `5061`
- Ramais que devem usar criptografia herdam do template
  `endpoint-secure` (que define `media_encryption=sdes` e
  `transport=transport-tls`) em vez de `endpoint-plain`

## Como testar manualmente
1. No softphone, crie a conta como **TLS** (não UDP), servidor
   `<ip>:5061`
2. Ative "SRTP obrigatório" nas opções avançadas do softphone (no
   Zoiper: Account → Advanced → Encryption)
3. Faça uma chamada entre dois ramais configurados assim — se o
   softphone mostrar um cadeado/ícone de chamada segura, está
   funcionando
4. Tente registrar o mesmo ramal via UDP puro na porta 5060 sem TLS —
   deve continuar funcionando (o transporte UDP não foi removido, só
   adicionado o TLS como opção), mas sem a proteção extra

## Teste automatizado
`tests/test_pjsip_conf.py::test_tls_transport_has_certificates`
`tests/test_pjsip_conf.py::test_secure_endpoints_use_encryption`

## Limitações conhecidas
- Certificado self-signed gera aviso de segurança em navegadores e
  alguns softphones até ser trocado por um certificado válido
- SRTP aqui é `sdes` (chave trocada dentro da sinalização SIP, que por
  sua vez está em TLS) — para telefones WebRTC, o método é `dtls` (ver
  manual 06), que é diferente e mais moderno
