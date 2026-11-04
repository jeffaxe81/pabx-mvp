# AXE PABX — Provisionamento mTLS (laboratório, issue #344)

## Entrega do próximo ciclo — não modifica o RC `v0.1.0-rc.1`

O gerador de arquivos `.cfg` contém senhas SIP. O serviço HTTP Nginx legado foi desativado por padrão no `docker-compose.yml`, e só existe no perfil explícito `insecure-lab-provisioning` publicado em `127.0.0.1`. **Não ativá-lo para telefones reais.**

Este lote adiciona `provisioning/mtls_server.py`: serviço HTTPS com certificado **de cliente obrigatório**, autorizado por SHA-256 do certificado DER, MAC e tenant. A política consulta o manifesto original `devices.json`, exigindo que `t1-1001` pertença a `t1` e que cada certificado esteja vinculado a um único MAC. O fabricante autorizado no laboratório é **Yealink**; outros necessitam homologação específica.

### Controles implementados

- Bind obrigatório em `127.0.0.1:8443`, **sem porta de rede externa**, sem alteração do Docker Compose.
- TLS mínimo 1.2, CA de clientes configurável, `ssl.CERT_REQUIRED` e certificado de servidor/chave definidos por argumentos.
- Cadastro privado em JSON 0600 (schema **v2**); chave TLS deve ser privada 0600, sem links simbólicos.
- Cadastro de cada MAC/certificado exige **valid_from**, **valid_until** (segundos Unix, janela máxima 30 dias) e **revoked** booleano. Sem campos ou datas válidas, a aplicação nega a leitura.
- Política privada recarregada **a cada GET**: revogar, expirar ou deixar o cadastro inacessível bloqueia novos downloads sem reiniciar o servidor. TLS ainda precisa verificar a validade do certificado e a cadeia da CA.
- Autorização fail-closed por SHA-256 de certificado cliente DER, MAC canônico de 12 hexadecimais e tenant confirmado por `ramal` do gerador; MAC e certificado não podem ser duplicados.
- Apenas `GET /<mac-lowercase>.cfg`, com método, rota e query estritamente validados; não há listagem de diretório.
- Diretório aberto em POSIX com `O_DIRECTORY | O_NOFOLLOW`; arquivos abertos relativamente ao FD do diretório, com `O_NOFOLLOW`; somente arquivo regular de até 512 KiB.
- Erros genéricos 404 sem divulgar existência do MAC, corpo da configuração ou metadados de outro tenant.
- Respostas `Cache-Control: no-store, private, max-age=0`, `Pragma: no-cache` e `X-Content-Type-Options: nosniff`.
- Sem registros de URLs, senhas SIP ou certificados no servidor HTTP de laboratório.
- Regressões de acesso cruzado, anonimato, fingerprint incorreto, MAC incompatível, traversal, URL com query, symlinks e **handshake TLS real** com CA e certificados efêmeros gerados pelo OpenSSL em testes.

### Forma de iniciar — apenas laboratório local autorizado

1. Gere **fora do repositório** uma CA de teste e certificados para o servidor e cada telefone/simulador; mantenha cada chave privada com permissão 0600. A autoridade de certificação do cliente usada aqui **não** pode ser a CA pública não relacionada ao provisioning.
2. Em diretório privado (0600), crie o cadastro com `schema_version:2` e entradas com `mac`, `tenant`, `client_sha256`, `valid_from`, `valid_until` e `revoked`. O hash é o SHA-256 dos bytes DER do certificado cliente. O MAC em minúsculas deve constar em `devices.json` com `ramal` do mesmo tenant. Cadastros antigos v1 **não são aceitos**; migrar explicitamente antes de iniciar o laboratório.
3. Gere arquivos no `provisioning/files` como de costume; certifique-se de que os nomes estejam em minúsculas, correspondendo aos MACs cadastrados.
4. Execute a ferramenta **somente na máquina de testes**, com chaves e cadastro fora da pasta pública:

```bash
python3 provisioning/mtls_server.py \
  --registry /diretorio-privado/certificados-dispositivos.json \
  --devices provisioning/devices.json \
  --files provisioning/files \
  --server-cert /diretorio-privado/servidor.crt \
  --server-key /diretorio-privado/servidor.key \
  --client-ca /diretorio-privado/ca-clientes.crt \
  --port 8443
```

O laboratório é acessível apenas em loopback; qualquer uso externo, túnel, redirecionamento de porta ou publicação precisa passar por revisão de segurança e homologação independente.

## Restrições e itens NÃO concluídos

**Produção NO-GO**. A configuração `.cfg` continua sendo gerada por padrão com modo 0644 por compatibilidade legada e pode ser lida por usuários locais autorizados ao sistema de arquivos; antes de produção, migrar a saída para diretório privado com permissões/identidade de serviço restritas. Não há token de uso único, CRL/OCSP, rotação automática de certificado, proteção contra negação de serviço, política de expiração de credenciais SIP, integração com rede corporativa nem gestão operacional de chaves. Revogação por marcação `revoked=true`, exclusão do dispositivo ou expiração do cadastro **não exige reiniciar**; é efetiva nos próximos GETs. Não substitui revogação de certificados pela CA em outros sistemas e não interrompe transferência já iniciada. Não foi homologado se o firmware Yealink disponibiliza certificado de cliente mTLS no fluxo de provisioning HTTPS.

O serviço não é incluído no `docker-compose.yml` nem publicado remotamente. A issue #344 permanece **aberta** até evidência com aparelho físico, autenticação/ACL operacional por tenant/MAC, segredos não expostos no host e revisão de suporte do fabricante.

**Não utilizar os resultados automáticos para elevar a homologação operacional ou autorizar deployment.**

## Formato v2 de registro privado (exemplo com valores fictícios)

O exemplo abaixo não contém credenciais reais e usa campos de validade ilustrativos. Antes de qualquer ensaio, gere datas Unix futuras com intervalo máximo de 30 dias e fingerprints reais do laboratório.

```json
{
  "schema_version": 2,
  "devices": [
    {
      "mac": "aabbccddeeff",
      "tenant": "t1",
      "client_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "valid_from": 1793400000,
      "valid_until": 1793486400,
      "revoked": false
    }
  ]
}
```

A alteração do arquivo deve ser atômica e restrita ao responsável pelo laboratório; guardar backup protegido e nunca versionar esses dados no GitHub. O serviço lê o arquivo a cada requisição e retorna 404 genérico diante de revogação, expiração, cadastro faltante ou inválido. O acesso a certificados e chaves de cliente ainda requer controles operacionais independentes.

## Operação local: inventário e revogação

Na raiz do projeto, use a CLI sobre o cadastro **v2 existente**. O console
deve pertencer ao operador que já tem acesso aos arquivos privados; a CLI
não oferece login remoto nem cria ou emite certificados.

```bash
python3 -m provisioning.certificates \
  --registry /diretorio-privado/certificados-dispositivos.json \
  --devices provisioning/devices.json list --tenant t1

python3 -m provisioning.certificates \
  --registry /diretorio-privado/certificados-dispositivos.json \
  --devices provisioning/devices.json revoke --tenant t1 --mac aabbccddeeff
```

O inventário retorna somente tenant, MAC, datas Unix e `status`: `pending`,
`active`, `expired` ou `revoked`. O filtro é exato (`t1` não inclui `t10`).
Não imprime fingerprint, certificado, chave ou senha SIP. `active` significa
apenas janela vigente e vínculo não revogado no cadastro; não verifica
expiração X.509, cadeia da CA, existência do `.cfg` ou disponibilidade do telefone.

A revogação exige tenant e MAC exatos, preserva as demais entradas e é
idempotente. Não há comando de reativação. O próximo GET autorizado pelo
servidor passa a retornar 404; downloads já iniciados não são interrompidos.

O diretório do cadastro deve ter modo 0700 (ou mais restritivo), pertencer
ao operador e não ser link simbólico. O cadastro deve permanecer privado
0600. A CLI usa um arquivo `<cadastro>.lock` privado e estável: **não o
apague ou substitua durante a operação**. Todos os escritores precisam
respeitar esse lock; editores externos não participam da serialização.
A leitura valida tipo, permissões e tamanho no descritor aberto com
`O_NOFOLLOW`; JSON excessivamente aninhado é rejeitado sem traceback.
A publicação usa JSON compacto (inclusive para os 5.000 dispositivos
suportados), temporário 0600, fsync e replace atômico.

Se a gravação falhar antes do replace, o cadastro original é preservado.
Uma falha de fsync do diretório depois do replace retorna erro e pode
significar que a revogação já foi publicada: consulte o inventário antes
de repetir. A CLI nunca desfaz uma revogação para tentar compensar esse erro.
Erros operacionais retornam código 2 com categoria genérica, sem caminho
ou conteúdo privado. Não modifica a configuração `.cfg`, não reinicia o
servidor e não substitui revogação por CRL/OCSP ou homologação Yealink físico.
