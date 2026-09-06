# Manual 04 — Tronco TDM (gateway)

## O que é
Permite que o PABX receba/faça ligações por uma linha telefônica
tradicional (analógica, E1 ou T1) através de um gateway físico que
converte TDM↔SIP. O Asterisk não fala TDM diretamente sem hardware
especializado (placas Digium/Sangoma) — o caminho padrão de mercado é
um gateway dedicado.

## Como configurar
1. Instale um gateway físico (ex: Grandstream GXW-410x, AudioCodes
   MP-11x, Patton SmartNode) e conecte a linha TDM nele
2. No gateway, configure ele para registrar/enviar SIP para o IP do
   servidor Asterisk, porta `5060`
3. Em `asterisk/pjsip.conf`, ajuste `match=192.168.1.200` na seção
   `[gateway-tdm]` (tipo `identify`) para o IP real do gateway
4. Em `asterisk/extensions.conf`, no contexto `[from-tdm-gateway]`,
   mapeie os DIDs (números que chegam pela linha) para o tenant/ramal
   corretos — hoje só existem dois exemplos fictícios
   (`5511900001111`, `5511900002222`)
5. Chamadas de **saída**: qualquer ramal disca `0` + número (ex:
   `01140028922`) e a chamada sai pelo tronco — isso já está no
   dialplan de cada tenant (`exten => _0.,1,Dial(...@gateway-tdm...)`)

## Como testar manualmente
Sem o gateway físico em mãos, dá pra simular parcialmente registrando
um segundo Asterisk (ou um softphone configurado como se fosse o
gateway) no mesmo IP/porta esperado, e discando `0` seguido de
qualquer número de um ramal para confirmar que a chamada tenta sair
pelo `gateway-tdm`. O teste real de verdade só acontece com o hardware
físico conectado.

## Teste automatizado
`tests/test_pjsip_conf.py::test_expected_endpoints_present` (garante
que o endpoint `gateway-tdm` continua existindo)

## Limitações conhecidas
- Não há teste automatizado que valide o comportamento real de uma
  chamada TDM (depende de hardware físico)
- DIDs mapeados em `[from-tdm-gateway]` são todos fictícios/exemplo —
  precisa substituir pelos números reais contratados
- Chamadas sem DID mapeado caem na telefonista (ramal 1000) por
  padrão — ver manual 06
