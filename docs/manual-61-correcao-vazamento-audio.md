# Manual 61 — Correção de vazamento de memória no player de áudio (item #61)

## O que fecha
O manual 60 (reprodução de áudio na lista do painel) documentou como
limitação: **"URLs de objeto (`createObjectURL`) não são revogadas —
cada clique em 'Reproduzir' acumula memória não liberada no
navegador"**. Este item fecha essa lacuna.

## O que é o problema
`URL.createObjectURL(blob)` cria uma referência que o navegador
mantém viva na memória até alguém explicitamente chamar
`URL.revokeObjectURL()` — ou até a página inteira ser fechada. Sem
isso, cada áudio tocado deixava uma URL "presa" na memória, mesmo
depois de trocar de áudio ou fechar a reprodução. Numa sessão de
painel aberta por horas, com um admin tocando vários áudios
diferentes pra conferir, isso acumula.

## A correção
`playSound()` guarda a última URL criada num atributo do próprio
elemento `<audio>` (`player.dataset.objectUrl`), e a **revoga antes**
de criar a próxima — assim nunca existe mais de uma URL "viva" por
vez.

```javascript
if (player.dataset.objectUrl) {
  URL.revokeObjectURL(player.dataset.objectUrl);
}
const objectUrl = URL.createObjectURL(blob);
player.dataset.objectUrl = objectUrl;
player.src = objectUrl;
```

## Por que revogar ANTES de criar a nova (não depois de tocar)
Esperar o áudio "terminar" pra revogar (evento `ended`) tem dois
problemas: o usuário pode trocar de áudio no meio da reprodução
(nunca disparando `ended`) ou navegar pra outra aba/fechar o painel
antes do fim. Revogar a URL anterior **no início da próxima
reprodução** é mais simples e cobre os dois casos sem precisar de
mais um listener de evento.

## Como testar
1. Abra o painel, gere ou reutilize alguns áudios diferentes
2. Toque vários em sequência (sem esperar nenhum terminar)
3. Confirme visualmente (DevTools → Memory, ou só pela ausência de
   comportamento anômalo) que não há acúmulo indefinido de URLs de
   objeto — cada nova reprodução revoga a anterior antes de criar a
   próxima

## Teste automatizado
- `tests/test_admin_html.py::test_play_sound_revokes_previous_object_url`
  — confirma que `URL.revokeObjectURL()` aparece no código **antes**
  de `URL.createObjectURL()`, garantindo a ordem certa
- **890 testes no total** (mesma contagem do manual 60 — este item
  corrigiu comportamento existente, sem adicionar rota nova nem
  módulo novo)

## Limitações conhecidas (honestidade técnica)
- **A última URL criada na sessão nunca é revogada explicitamente**
  — só é liberada quando a aba/painel fecha (comportamento padrão do
  navegador, aceitável: uma URL não revogada no fim da sessão não é
  o mesmo problema que acumular várias ao longo da sessão)
- **Sem teste automatizado de uso de memória real** — o teste
  confirma a *ordem* do código (revogar antes de criar), não mede
  memória de verdade num navegador rodando; isso exigiria uma
  ferramenta de teste de navegador (ex: Playwright/Selenium), fora do
  escopo dos testes estáticos deste projeto
