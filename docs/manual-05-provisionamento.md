# Manual 05 — Auto-provisionamento

## O que é
Um telefone físico (Yealink, por enquanto) liga, busca sua própria
configuração num servidor HTTP pelo MAC address, e já sobe registrado
— sem digitar nada manualmente no aparelho.

## Como configurar
1. Cadastre o telefone em `provisioning/devices.json`: MAC, fabricante
   (`vendor`), ramal, nome, senha e servidor
2. Rode `python3 provisioning/generate.py` — gera
   `provisioning/files/<MAC>.cfg` a partir do template do fabricante
   em `provisioning/templates/`
3. Configure o telefone físico para buscar o arquivo de provisionamento
   em `http://<ip-do-servidor>:8080/` (o mecanismo de descoberta - DHCP
   option 66, PnP multicast, ou digitar a URL manualmente - depende do
   fabricante e é feito no próprio aparelho)

Para suportar um fabricante novo (Grandstream, Cisco, Snom...):
1. Crie um template em `provisioning/templates/<fabricante>.cfg.tpl`
   no formato que aquele fabricante espera
2. Adicione a entrada em `TEMPLATE_EXT` dentro de `generate.py`

## Como testar manualmente
1. Rode `python3 provisioning/generate.py`
2. Confira o arquivo gerado em `provisioning/files/<MAC>.cfg` — as
   variáveis `{{RAMAL}}`, `{{SENHA}}` etc. devem ter sido todas
   substituídas
3. Com o container `provisioning` rodando (`docker compose up -d`),
   acesse `http://localhost:8080/<MAC>.cfg` no navegador e confirme
   que o conteúdo aparece

## Teste automatizado
`tests/test_provisioning.py` — roda o gerador de verdade contra um
`devices.json` de teste e garante que nenhum `{{placeholder}}` sobra,
e que um fabricante desconhecido não derruba o script.

## Limitações conhecidas
- Só existe template para Yealink
- Os arquivos `.cfg` gerados contêm senha em texto plano — por isso
  ficam fora do Git (`.gitignore`); em produção, considere servir via
  HTTPS para não trafegar a senha em texto plano na rede também
- Não há interface web pra cadastrar dispositivos — é editar o
  `devices.json` na mão
