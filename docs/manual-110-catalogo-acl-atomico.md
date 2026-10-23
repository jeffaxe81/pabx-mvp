# Manual 110 — Catálogo ACL de gravações sem corrida de symlink

## Objetivo
Reforçar a fronteira de acesso às gravações no marco 8, complementando
as proteções de download registradas nos Manuais 107–109.

## Defeito identificado
O carregador de ACL chamava \`Path.is_symlink()\`, \`Path.is_file()\`,
\`stat()\` e \`read_text()\` em operações distintas sobre o caminho.
Um processo que pudesse alterar o volume entre a inspeção e a leitura
poderia substituir o arquivo por symlink e fornecer uma ACL diferente
daquela validada. Esse é um risco TOCTOU (*time of check to time of use*).

## Correção
\`queue-api/recording_access.py\` agora:
- Exige \`O_NOFOLLOW\` e \`O_NONBLOCK\` no sistema operacional; sem
  suporte, falha fechado em vez de ler um caminho inseguro.
- Abre o catálogo uma única vez com \`os.open()\` e verifica \`fstat()\`
  sobre o mesmo descritor.
- Rejeita arquivos não regulares, links simbólicos, catálogos acima
  de 1 MiB e JSON inválido.
- Limita a leitura a \`MAX_POLICY_BYTES + 1\`, mesmo caso um terceiro
  processo aumente o arquivo depois de \`fstat()\`.
- Conserva a validação existente de hashes de tokens, validade,
  tenant, proprietário, papel e arquivo.

O catálogo continua sendo lido a cada requisição de gravação:
a revogação de uma credencial na política entra em vigor sem restart.

## Testes
\`\`\`bash
cd queue-api
python3 -m pytest -q tests/test_recording_policy_atomic_read.py
\`\`\`

Cobertura: leitura válida, symlink pré-existente, FIFO, arquivo acima do
limite, troca por symlink imediatamente **após** a abertura do FD,
alternância entre política válida/inválida, crescimento concorrente de
arquivo após \`fdopen()\` e revogação entre leituras.

## Reforço — proteção de pastas ancestrais
A abertura anterior usava \`O_NOFOLLOW\` apenas no nome final do
catálogo. Isso não impede que uma pasta intermediária da árvore de
diretórios seja um link simbólico. A rotina \`_open_policy_file\`
passa a percorrer cada diretório com \`openat(dir_fd=...)\`,
\`O_DIRECTORY\` e \`O_NOFOLLOW\`, mantendo descritores dos ancestrais
abertos durante a resolução até o arquivo final.

Novas regressões cobrem symlink em ancestral direto ou intermediário,
substituição de pasta por symlink imediatamente depois da abertura do
diretório, \`..\` no caminho e leitura do arquivo originalmente aberto.
Exige POSIX/Linux com \`dir_fd\`; em plataforma sem esse suporte,
a política de gravações é negada por padrão.

## Limites e critério de aceite
São testes automatizados em arquivos temporários, não chamadas reais,
não pentest com privilégios do host nem prova HTTP multiempresa ponta
a ponta. Não substituem a homologação de isolamento de ramais,
fila, voicemail, DIDs e gravações com t1/t2/t3.

O marco 8 só pode passar para concluído depois do conjunto de
evidências reais. Programa permanece em 7/16 (43,8%);
\`operational_go_authorized\` permanece falso.
