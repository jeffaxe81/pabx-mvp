# Manual 85 — Escrita atômica e concorrência no cadastro de ramais

## Falha corrigida

O `admin-api/store.py` escrevia `extensions_store.json` diretamente
com `Path.write_text`. Se o processo fosse interrompido ou o volume
falhasse durante a escrita, o arquivo anterior poderia ficar truncado.
Além disso, o `ThreadingHTTPServer` atende requisições paralelas:
duas criações simultâneas podiam carregar o mesmo snapshot e uma
sobrescrever a atualização da outra.

O arquivo inclui credenciais SIP e PINs de correio de voz, portanto
o armazenamento precisa ser restrito.

## Implementação

1. `save_store()` cria um arquivo temporário no mesmo diretório do
   destino, com permissão Unix `0600`.
2. Grava o JSON completo, executa `flush()` e `fsync()`, depois
   troca o arquivo pelo novo com `os.replace()`.
3. Se a serialização ou a troca falhar, o temporário é apagado e
   o snapshot anterior permanece intacto.
4. `load_store()` rejeita links simbólicos, conteúdo que não seja
   lista JSON e arquivos não regulares; JSON inválido **não** vira
   cadastro vazio.
5. As rotinas de adicionar, editar, remover e excluir ramais por tenant
   utilizam uma trava reentrante durante toda a sequência de
   carregar, validar e salvar.

Essa mudança não modifica senhas, PINs, ramais, tenants nem o conteúdo
funcional gerado para Asterisk.

## Testes automatizados

```bash
(cd admin-api && python3 -m pytest -q tests/test_store.py)
```

Cenários adicionais cobrem falha durante a escrita, falha no
`os.replace()`, ausência de arquivos temporários órfãos, permissões
`0600`, leitura segura de JSON inválido, bloqueio de symlinks,
30 cadastros simultâneos com IDs distintos e duplicação simultânea
de um mesmo número — apenas uma criação deve ser aprovada.

## Limitações operacionais

- A trava `threading.RLock` sincroniza **apenas threads do mesmo
  processo Python**. Não substitui locking distribuído entre
  containers, processos ou servidores. A implantação deve manter
  apenas uma instância escritora do cadastro, ou adotar banco com
  transações e travas compartilhadas.
- A publicação atômica evita arquivo parcialmente escrito, mas não
  realiza transação distribuída entre JSON, configuração Asterisk,
  AstDB e AMI. O reload e a homologação continuam necessários.
- Um `fsync()` do arquivo temporário reduz o risco de perda na
  escrita; a durabilidade sob falha elétrica do sistema de arquivos
  depende também da política de sync do diretório/volume.
- Depois da implantação, confirmar permissões e acesso dos serviços
  que precisam ler `extensions_store.json`, além de backup/restauração.
- Nenhuma chamada SIP/RTP nem instalação real é executada pelos testes.

O aceite operacional depende da matriz do [Manual 73](manual-73-gates-homologacao.md).
