# AXE PABX puro — 30 controles de provisionamento IP

**Escopo:** geracao de arquivos de configuracao de telefones IP, sem Contact Center nem IA. Os codigos PV-01..PV-30 sao 30 verificacoes negativas independentes, nao 30 novos produtos ou funcionalidades visiveis ao usuario.

| ID | Controle | 
|---|---|
| PV-01 | Catalogo nao e um arquivo regular ou e link simbolico |
| PV-02 | Limite de tamanho do catalogo (2 MiB) |
| PV-03 | JSON invalido ou codificacao invalida |
| PV-04 | Raiz do catalogo deve ser objeto |
| PV-05 | Lista devices obrigatoria |
| PV-06 | devices deve ser uma lista |
| PV-07 | Limite de 5000 dispositivos por lote |
| PV-08 | Registro de dispositivo deve ser objeto |
| PV-09 | MAC obrigatorio |
| PV-10 | MAC como texto (nao inteiro/bool) |
| PV-11 | MAC de 12 caracteres hexadecimais |
| PV-12 | MAC unico sem diferenciar maiusculas |
| PV-13 | Fabricante obrigatorio |
| PV-14 | Fabricante como texto |
| PV-15 | Fabricante nao vazio |
| PV-16 | Ramal obrigatorio para fabricante suportado |
| PV-17 | Nome obrigatorio |
| PV-18 | Senha SIP obrigatoria |
| PV-19 | Servidor SIP obrigatorio |
| PV-20 | Campos SIP como texto |
| PV-21 | Rejeicao de campos vazios |
| PV-22 | Bloqueio de CR/LF/NUL e outros controles |
| PV-23 | Bloqueio de interpolacao de marcadores em dados |
| PV-24 | Limites de tamanho de ramal/nome/senha/servidor |
| PV-25 | Template precisa existir e nao ser link simbolico |
| PV-26 | Tamanho maximo de template e configuracao |
| PV-27 | Template com codificacao UTF-8 valida |
| PV-28 | Quatro placeholders obrigatorios no template |
| PV-29 | Marcadores desconhecidos ou residuais bloqueados |
| PV-30 | Bloqueio de symlink do diretorio/arquivo de destino |

## Comportamento implementado

- Validacao de todos os dispositivos e renderizacao antes de gravar qualquer arquivo (falha antecipada).
- Substituicao individual atomica: arquivo temporario no mesmo diretorio, sincronizacao de dados e troca via os.replace. Se a troca falhar, o arquivo anterior permanece e o temporario e removido.
- Fabricante desconhecido continua produzindo aviso e sendo ignorado para preservar compatibilidade.
- Regressao automatizada: tests/test_provisioning_30_guardas.py, incluindo isolamento de credenciais de dois tenants e erros de gravacao.

## Limites e pendencias

- A publicacao nao e uma transacao atomica de todo o lote; operacoes ja realizadas permanecem se uma posterior falhar.
- Arquivos .cfg possuem credenciais SIP. O modo 0644 mantem compatibilidade com o servidor HTTP atual, mas **nao fornece autenticacao nem controle de acesso ao endpoint**. Precisa ser corrigido por outra entrega.
- Nenhum telefone fisico, chamada SIP, TLS/SRTP real ou ambiente de producao foi homologado por este lote. Nao modifica o percentual formal da release sem os criterios aplicaveis.
