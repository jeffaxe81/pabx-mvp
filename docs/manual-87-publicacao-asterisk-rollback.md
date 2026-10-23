# Manual 87 — Publicação recuperável do Asterisk e migração de volumes

## Problema e limite do conserto

O backend administrativo escrevia vários `.conf` do Asterisk diretamente
na pasta, um após o outro. Falhas durante a escrita ou no AMI podiam
deixar arquivos truncados ou um conjunto parcialmente publicado.

Outro risco: o Compose montava cada arquivo dinâmico como **bind mount
individual**. Um `os.replace()` troca o inode do arquivo no host e
**não atualiza o inode já montado dentro do container**. Por isso, usar
somente `os.replace` sem mudar o Compose produziria reload de arquivos
antigos. Ambos os problemas são tratados em conjunto neste ciclo.

## Implementação

- `admin-api/conf_publisher.py` prepara todos os conteúdos em arquivos
  temporários do mesmo diretório, com `fsync` e permissão preservada.
- Os arquivos só são substituídos após todos os temporários estarem
  prontos. Em exceção durante a publicação ou o reload, os snapshots
  anteriores são restaurados e arquivos inéditos são removidos.
- `regenerate_and_reload()` verifica ACKs de PJSIP, dialplan, voicemail,
  filas e estacionamento. Respostas `Error`/ausentes provocam rollback.
  Após restaurar os arquivos, tenta recarregá-los pelo AMI novamente.
- Diretório `asterisk/generated/` agora é montado como um único volume
  de diretório, **somente leitura dentro do Asterisk**. O admin-api
  permanece com acesso de escrita via volume `./asterisk`.
- `pjsip.conf`, `extensions.conf`, `voicemail.conf` e os contextos
  dos tenants criados pelo wizard incluem arquivos em `generated/`.
- Os arquivos iniciais de t1/t2 são versionados em `asterisk/generated`
  para que a primeira instalação possua os includes necessários.

## Migração obrigatória para instalações existentes

**A migração é uma mudança de infraestrutura, não apenas de código.**
Exige janela de manutenção e recriação do container Asterisk. Antes
de atualizar, faça backup completo dos dados do admin-api, AstDB e
arquivos Asterisk e teste a restauração. **Não execute este roteiro
diretamente sobre produção sem aprovação operacional.**

1. Parar alterações pelo painel, registrar commit atual e garantir
   a janela de manutenção.
2. Guardar cópia independente de `asterisk/`, dados do admin-api,
   gravações e configuração do Compose.
3. Após atualizar o código, **antes de iniciar o novo Compose**,
   copiar os arquivos dinâmicos existentes para a nova pasta, pois
   os arquivos versionados t1/t2 são modelos vazios:

   ```bash
   mkdir -p asterisk/generated
   for file in asterisk/pjsip_dynamic.conf \
       asterisk/extensions_dynamic_dial-*.conf \
       asterisk/extensions_dynamic_hints-*.conf \
       asterisk/voicemail_dynamic_*.conf; do
     [ -f "$file" ] || continue
     cp -p "$file" "asterisk/generated/$(basename "$file")"
   done
   ```

4. Conferir que os arquivos copiados correspondem ao cadastro dos
   ramais (inclusive tenants t3+) e que o diretório é legível pelo
   Asterisk. Não divulgar senhas SIP nos relatórios.
5. Recriar o serviço Asterisk com o novo Compose. Nunca usar
   `docker compose down -v` neste procedimento: essa opção remove
   volumes de dados.
6. Executar a verificação `pjsip show endpoints`,
   `dialplan show t1-internal`, `dialplan show t3-internal`
   (se t3 existir), e validar chamadas de laboratório.
7. Em caso de falha, seguir o rollback aprovado do release inteiro,
   inclusive as montagens antigas; não misturar versões de arquivo,
   Compose e imagens.

## Testes automatizados

```bash
(cd admin-api && python3 -m pytest -q tests/test_conf_publisher.py)
python3 -m pytest -q tests/test_docker_compose.py \
  tests/test_extensions_conf.py tests/test_pjsip_conf.py tests/test_voicemail_conf.py
```

Os testes simulam interrupção no segundo arquivo, erro AMI,
restauração dos bytes/modo antigos, remoção de arquivo novo, defesa
contra symlinks e caminhos inseguros. Também conferem o volume de
diretório e os includes estáticos.

## Limitações importantes

**Não é uma transação global multi-arquivo.** Enquanto arquivos são
substituídos individualmente, outro leitor pode observar uma mistura
temporária. O Asterisk recebe reload somente após o último arquivo,
mas mudanças manuais ou outro processo escritor podem interferir.

**Rollback AMI é best effort.** Um `Response: Follows` confirma
que a resposta do comando chegou; não comprova o sucesso semântico
de cada comando do CLI. Se a rede ou AMI estiver indisponível, pode
ser impossível reaplicar automaticamente a configuração anterior.

**AstDB e dados JSON não são revertidos por esta rotina.** Ações AMI
extras e gravações no cadastro de ramais podem ter ocorrido antes do
erro. Operações de criação/remoção de tenant e seus arquivos estáticos
também exigem gestão específica de rollback.

**Durabilidade e concorrência:** snapshot restaurado em falha não
substitui backup; múltiplas instâncias administrativas escrevendo no
mesmo volume exigem locking compartilhado. A atualização de mounts
necessita validação real em Docker e a homologação do Manual 73.

Nenhuma implantação nem chamada SIP/RTP foi feita por esta PR.

## Verificação automatizada da migração (Manual 88)

Antes da recriação do Asterisk, use o [pré-check somente leitura](manual-88-precheck-gerados-asterisk.md)
para verificar presença dos arquivos, includes e possíveis diferenças
entre configurações antigas e novas. A ferramenta não migra arquivos
e não comprova a instalação no Docker.

## Complemento — respostas AMI completas (Manual 90)

O cliente administrativo passou a correlacionar as respostas por
`ActionID` e aguardar os blocos AMI completos, inclusive quando a
resposta chega fragmentada no TCP. Isso reduz falsas decisões de
recarga por leitura parcial. Consulte o [Manual 90](manual-90-ami-tcp-framing.md).
