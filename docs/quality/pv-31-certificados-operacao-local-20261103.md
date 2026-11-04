# AXE PABX — operação local de certificados de provisionamento

Base: `dcf3a9cb7055b52f4a1b9e2f91c58780afa5c061`. Continuidade da issue #344.

## Entrega

- Inventário por tenant exato, com estados de validade e sem certificado,
  fingerprint, chave privada ou senha SIP na saída.
- Revogação por tenant/MAC, idempotente, com preservação de outras empresas,
  lock estável e escrita atômica privada 0600.
- Leitura segura do cadastro no mesmo descritor: sem corrida entre stat
  e abertura, sem symlink final, tipo regular e tamanho limitado.
- JSON de cadastro exige versão inteira 2; dados excessivamente aninhados
  são negados sem traceback. Cadastro válido de 5.000 dispositivos pode
  ser revogado sem exceder o limite por expansão da formatação.

## Verificação local

O teste inicial de leitura reproduziu obtenção de outro arquivo após
troca por symlink; o teste de schema reproduziu aceitação de `2.0`.
Ambos falharam antes da correção e passaram depois.
As operações novas falharam inicialmente por ausência do módulo.
Na revisão independente, foram reproduzidos bloqueio de revogação em
5.000 dispositivos e erro não sanitizado em JSON aninhado. As duas
regressões falharam antes da correção e passaram depois.

| Suíte | Resultado local |
| --- | ---: |
| Configurações/web/provisioning | 623 aprovados |
| admin-api | 7.663 aprovados |
| queue-api | 1.221 aprovados |
| ai-worker (somente regressão existente) | 94 aprovados |
| asterisk/agi | 19 aprovados |
| asterisk/scripts | 8 aprovados |
| backup | 1.025 aprovados |
| scripts | 3.584 aprovados |
| **Total Python** | **14.237 aprovados** |
| Node | 25 aprovados |

Comandos: `python -m pytest -q tests` em cada diretório da matriz
`quality-gates.yml`; `npm run test:node`; `git diff --check`;
`python -m compileall -q provisioning`.
Os 38 casos novos compreendem 36 testes da operação local e dois da
leitura/versão. O teste mTLS preexistente foi ampliado para executar a
CLI real contra servidor HTTPS ativo: 200 antes, 404 após revogação,
outro tenant permanece 200. OpenSSL usa CA/certificados efêmeros locais.
O teste de concorrência usa dois processos reais, sem simular o lock.

## Limites

Os resultados acima são locais; a CI e os laboratórios Asterisk devem
ser conferidos no SHA da PR antes de integrar. Não há novo teste SIP
real local nesta entrega, emissão/rotação de certificados ou publicação
de serviços. Nenhuma função de Contact Center/IA foi implementada.

Yealink físico, proteção operacional dos `.cfg`, integração administrativa
e demais provas de ambiente-alvo permanecem pendentes. A issue #344
continua aberta; não altera o RC `v0.1.0-rc.1`, os 13 cenários de
homologação ou as 15 provas operacionais. **Produção NO-GO.**
