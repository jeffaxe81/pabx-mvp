# 66. Interface AXE PABX no padrão visual do Despacho

## O que mudou

As telas de telefonista, operação, campanhas, relatórios e administração
passam a usar o padrão do Despacho: fundo claro, cartões brancos,
destaque azul-petróleo, menu lateral com ícones, cabeçalho e controles
com foco visível. Referência: `jeffaxe81/dispatch`, commit
`3aee47e889c30f8cf9ae858e5d05ebf35c64691b`, arquivos
`client/src/index.css` e `client/src/components/DashboardLayout.tsx`.

A telefonista mostra uma orientação enquanto não há uma tela de chamada
visível. Essa orientação acompanha os estados que o console existente
já controla. Os atalhos para outras telas abrem em outra aba para não
descarregar o console durante uma chamada.

A administração deixa de apresentar todos os formulários em uma única
lista. O menu organiza os recursos em:

| Seção | Recursos existentes |
|---|---|
| Ramais | Listagem, cadastro e edição |
| Atendimento | Modo feriado, overflow e clientes VIP |
| Segurança | Bloqueio de números, 2FA e PIN de monitoramento |
| Usuários | Contas e perfis |
| Empresas | Wizard de tenants |
| Áudios e IA | Geração TTS e lista de áudios |

As restrições de login e de perfil permanecem nas APIs e no código
existente. Supervisores continuam sem os formulários de alteração
reservados a administradores. Seções que só contêm recursos de
administrador ficam ocultas para o supervisor.

## Configuração e acesso

No Compose atual:

- Telefonista: `http://<servidor>:8082/index.html`
- Operação: `http://<servidor>:8082/painel-operacional.html`
- Campanhas: `http://<servidor>:8082/campanhas.html`
- Relatórios: `http://<servidor>:8082/relatorios.html`
- Administração: `http://<servidor>:8091/`
- API das filas: conforme configuração atual, normalmente porta 8090.

O menu usa o host atual e essas portas. Na telefonista, a API preenchida
no campo de conexão é mantida nos atalhos para operação, campanhas e
relatórios. A preferência de menu recolhido é salva localmente no
navegador; se o armazenamento estiver indisponível, o menu continua
funcionando sem persistência.

Para uma instalação com proxy reverso, configure as URLs dos portais:

```text
https://pbx.exemplo.com/phone/index.html?api=https%3A%2F%2Fapi.exemplo.com&web=https%3A%2F%2Fpbx.exemplo.com%2Fphone%2F&admin=https%3A%2F%2Fadmin.exemplo.com%2F
```

`web` é a URL do diretório que contém as quatro páginas do webphone,
com barra final; `admin` é a URL exata da página de administração;
`api` é a base da API de filas. Somente URLs HTTP/HTTPS sem usuário ou
senha embutidos são aceitas. O menu transporta apenas esses três
parâmetros; credenciais, tenant e outros parâmetros não são copiados.

Ao navegar para a administração, a configuração fica no fragmento
`#axe?...`, que não é enviado ao servidor. Isso preserva a compatibilidade
com o `admin-api`, que serve `/` e `/index.html` sem novas rotas estáticas.
A configuração de proxy e os certificados continuam sendo os da
implantação. Esta alteração não configura o proxy.

## Manutenção

CSS e navegação comuns ficam em `ui/axe-ui.css` e `ui/navigation.js`.
O sincronizador insere cópias nas cinco páginas e preserva os scripts
de telefonia e as chamadas de API:

```bash
python3 scripts/sync_ui.py
python3 scripts/sync_ui.py --check
```

O segundo comando falha se uma página estiver fora de sincronia. As
páginas já versionadas estão prontas para os servidores atuais; não é
necessário instalar Node.js no servidor para executá-las.

A versão do cache da PWA foi incrementada para retirar o HTML anterior
do cache. O manifest usa as cores do novo tema. A atualização de uma
PWA já instalada depende do ciclo normal de atualização do navegador;
se necessário, feche e abra novamente a aplicação.

## Teste manual

1. Abra as cinco telas e confira o item ativo no menu, o cabeçalho,
   formulários, tabelas e indicadores.
2. Recolha o menu no desktop e recarregue: a preferência deve permanecer.
3. No celular, abra o menu, feche tocando fora ou usando Escape com um
   teclado; o foco volta ao botão do menu.
4. Conecte a telefonista em um ambiente de teste: a orientação inicial
   deve dar lugar ao discador. Abra outro portal pelo menu e confira que
   o console continua aberto.
5. Entre na administração com perfis admin e supervisor. Troque as
   seções e o tenant; confira que a administração das permissões segue
   o comportamento anterior. Saia e confira que os formulários somem.
6. Confira o discador também em tablets e celular, sem rolagem
   horizontal da página. Tabelas extensas podem rolar dentro do cartão.
7. Faça o teste real de registro SIP, chamada, transferência e áudio
   previsto nos manuais anteriores. Os testes de interface abaixo
   não substituem esse teste no Asterisk.

## Testes automatizados

```bash
python3 -m pytest tests/ -q
node --test tests/ui_navigation.test.cjs
python3 scripts/sync_ui.py --check
```

`tests/test_ui_sync.py` verifica sincronização idempotente e preservação
de conteúdo existente. A suíte Node de navegação verifica portas,
prefixos de proxy, API configurada, retorno da administração e rejeição
de URLs inválidas/credenciais embutidas.

Suíte opcional de navegador, para uma máquina de desenvolvimento com
Node.js e Chromium:

```bash
npm install --no-save playwright
npx playwright install chromium
node --test tests/ui_browser.test.cjs
```

Pode-se apontar um Chromium existente por `PABX_BROWSER_EXECUTABLE`.
Os testes abrem o HTML real com respostas de API sintéticas: conferem
carregamento, navegação, foco, recolhimento, perfis e largura do
discador entre 360 e 1366 pixels. Não fazem chamadas SIP nem validam
RTP, SIP trunks, qualidade de áudio ou a integração real com o Despacho.

## Rollback

Reverta o commit desta interface no Git e atualize os arquivos montados
pelo Compose. O rollback não exige migração de dados: esta alteração
não muda o banco, o dialplan, as APIs ou os serviços de telefonia.
