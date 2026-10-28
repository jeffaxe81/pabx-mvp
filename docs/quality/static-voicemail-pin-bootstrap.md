# Segurança do voicemail estático — preparação de PINs (Marco 8, parcial)

## Problema
As sete caixas de voz versionadas em `asterisk/voicemail.conf` (t1/t2)
usavam um PIN de exemplo compartilhado. A simples separação de contextos
`*97` não comprova segurança de autenticação da caixa postal.

## Mudança na configuração versionada
Cada mailbox estática passa a ter seu próprio placeholder
`troque_esta_senha_vm_...` (nenhum PIN real é versionado).
`python3 scripts/generate_secrets.py` gera PINs decimais de oito
dígitos distintos para essas caixas, além dos demais segredos SIP/AMI.
O verificador `scripts/verify_deployment.py` reprova placeholders
não substituídos e falta do arquivo de voicemail.

O laboratório Asterisk gera outros PINs efêmeros na sua cópia isolada:
não utiliza dados de clientes, não altera o checkout e não imprime PINs
na evidência.

## Procedimento operacional
- Preparar os segredos **antes** de iniciar os serviços.
- Distribuir os PINs individuais por canal protegido, com guarda em cofre.
- Nunca publicar o conteúdo já provisionado de voicemail.conf em Git
  público ou anexar PINs a logs e artefatos de CI.
- Rotacionar **manualmente e sob autorização** os PINs legados já
  instalados. A mudança do arquivo versionado não atualiza um
  servidor existente nem demonstra rotação feita.

## Limites e gate
Esta PR corrige apenas o bootstrap do arquivo estático. Ainda faltam
ensaios reais de PIN errado/correto, tentativas repetidas, acesso
à mailbox de outro tenant, proveniência e isolamento do volume.
Não fechar o Marco 8 e não autorizar GO operacional por esta mudança.
Acompanhar a issue #88.
