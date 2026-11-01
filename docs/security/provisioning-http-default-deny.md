# AXE PABX — bloqueio do HTTP legado de provisionamento (issue #344)

**Escopo: PABX puro.** Os arquivos `.cfg` gerados em
`provisioning/files` contêm **senhas SIP em texto claro**. A distribuição
anterior usava Nginx sem autenticação em `0.0.0.0:8080`. **Isto não é seguro
para uso em rede ou produção.**

## Mudança implementada

- O serviço `provisioning` no `docker-compose.yml` pertence agora apenas
  ao perfil opt-in `insecure-lab-provisioning`.
- `docker compose up` sem perfis NÃO inicializa o Nginx de arquivos `.cfg`.
- Mesmo no perfil de laboratório, a porta é publicada somente em
  `127.0.0.1:8080`; volumes permanecem somente leitura e restart é `no`.
- O preflight estático
  `python3 scripts/provisioning_exposure_preflight.py`
  rejeita perfis implícitos, endereço público, rede host, portas alternativas,
  volumes graváveis e montagem da pasta sensível em outros serviços.
- Não foi instalado servidor TLS/autenticado e **nenhum telefone real foi
  homologado**. O perfil é explicitamente inseguro, mesmo em loopback.

```bash
python3 scripts/provisioning_exposure_preflight.py
python3 -m pytest -q tests/test_provisioning_default_deny.py
```

Se um operador **deliberadamente** ativar esse perfil, deve fazê-lo apenas
em laboratório descartável, no mesmo host, usando **credenciais sintéticas**
sem relação com contas/ramais reais. Não usar telefones externos, túnel,
port-forward, proxy reverso ou redes compartilhadas para alcançar 8080.
Logs e backups locais também precisam de proteção.

## Limitação de migração e implantação

Esta PR **não executa deploy nem encerra containers antigos**. Uma instância
Nginx previamente iniciada pode **continuar expondo** os arquivos por HTTP
até que o administrador execute uma migração controlada e confira o estado
real do host. A mudança do Compose não revoga senhas SIP já expostas.

Antes de qualquer uso real, auditar containers/portas existentes, retirar
publicação pública, revisar acessos aos arquivos e rotacionar credenciais
caso se suspeite de exposição. Fazer isso com plano de backup e rollback.

## Itens ainda necessários para encerrar #344

1. Distribuição **HTTPS com certificado confiável** e autenticação por
   dispositivo; nenhum segredo na URL ou logs.
2. Autorização por tenant/MAC, expiração, antifraude/replay e controle de
   diretório, cache, traversal e acesso anônimo.
3. Testes negativos de credenciais incorretas/expiradas e isolamento cruzado.
4. Homologação específica em **Yealink físico de laboratório**, incluindo
   mecanismos realmente suportados pelo firmware.
5. Decisão humana independente antes de liberar qualquer ambiente real.

**Decisão: PRODUÇÃO NO-GO.** Este trabalho é somente mitigação de
exposição acidental por padrão e não fecha a issue #344. A RC
`v0.1.0-rc.1` permanece sem alteração.
