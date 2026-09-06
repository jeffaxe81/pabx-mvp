<?xml version="1.0" encoding="UTF-8"?>
<!--
  Template de auto-provisionamento Yealink (formato .cfg simplificado
  em XML só para leitura; na prática o Yealink usa .cfg puro texto,
  mas manter comentado para consulta rápida).

  O arquivo REAL fica em provisioning/files/<MAC>.cfg
  Ex: 805ec0aabbcc.cfg
-->

# ---- account.cfg equivalente (Yealink usa key=value, sem XML) ----
account.1.enable = 1
account.1.label = {{RAMAL}}
account.1.display_name = {{NOME}}
account.1.user_name = {{RAMAL}}
account.1.auth_name = {{RAMAL}}
account.1.password = {{SENHA}}
account.1.sip_server.1.address = {{SERVIDOR}}
account.1.sip_server.1.port = 5061
account.1.sip_server.1.transport_type = 2   ; 2 = TLS
account.1.srtp_encryption = 1               ; força SRTP
account.1.nat.udp_update_enable = 1
