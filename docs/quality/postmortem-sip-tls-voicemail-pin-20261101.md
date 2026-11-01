# AXE PABX — investigação da falha intermitente SIP/TLS em 01/11/2026

**Escopo:** laboratório descartável GitHub Actions, sem acesso ao ambiente de cliente ou produção. **Status:** causa provável identificada; o diagnóstico original não contém dados suficientes para atribuir causalidade com certeza.

## Evidências primárias verificadas

- PR #362; execução Asterisk `41343354013`, mesmo SHA fonte `5448ae43ea54e1c4e5bf365f18ed0cff21766e30` nas duas tentativas e mesmo checkout sintético `014bc182e770628ff960464c50c9c7dcd9358b65`.
- **Tentativa 1:** job `124957885824`, relatório de artefato `13098127056`: `checkout_clean=true`, resultado `FAIL`, `error_type=ValueError`, `error_reason=other`, sem `phase`, sem `image_id`, apenas **1/1** check. Tempo do evento 19:45:54 UTC.
- **Tentativa 2:** job `124958477731`, artefato `13097599769`: **22/22 PASS**, Asterisk **22.11.0**, TLS 1.2, digest Docker `sha256:d6333b8b331563c5887b98b12da9371ef48317e657d17d81770fe085f335041d`, check dos registros t1/t2/t3 aprovado. Tempo do evento 19:48:17 UTC.
- O job falhou antes de executar `docker pull`/`docker create`, segundo a ausência dos campos do relatório que são definidos na sequência de inicialização. **Não há evidência de erro da imagem Docker, TLS ou REGISTER** na primeira tentativa.
- O erro original poderia surgir de diferentes `ValueError` na preparação. O relatório não gravava a etapa e ocultava o texto não allowlisted; portanto **não permite provar exatamente qual condição ocorreu**.

## Hipótese prioritária reproduzível

No bootstrap original `lab/asterisk_lab.py`, cada PIN efêmero para t1/t2 era aceito se fosse apenas *diferente dos anteriores*, enquanto `validate_prepared_voicemail` também rejeita PINs com poucos dígitos distintos e valores fracos conhecidos. A geração aleatória `scripts/secrets_generator.py:generate_voicemail_pin()` escolhe um número uniforme de oito dígitos e **pode produzir uma amostra inválida**. O gerador dinâmico de t3 operava em conjunto separado: uma colisão entre t3 e t1/t2, ainda que improvável, também reprovaria o preflight.

A rotina de validação final deve continuar rejeitando configurações fracas. A correção é **regenerar amostras inadequadas antes do estágio de configuração**, com limite explícito de tentativas e conjunto único compartilhado entre t1/t2/t3, sem reduzir as exigências do validador.

O fluxo anterior pode ser demonstrado em teste com amostra fraca sintética, forçando a falha de configuração sem depender de sorte no CI. O novo teste injeta uma amostra fraca e confirma que o bootstrap termina com PINs validados e distintos. Outro teste esgota deliberadamente as tentativas e exige recusa sem imprimir PIN.

## Medidas no código

1. `lab/voicemail_pin_checks.py`: `generate_verified_lab_pin_map`, gera no máximo 64 amostras por PIN; descarta sequências, repetições, colisões e PINs fracos; erro sem valores em claro.
2. `lab/asterisk_lab.py`: um conjunto de PINs para as dez mailboxes t1/t2/t3, reutilizado pelo renderizador do tenant dinâmico; o preflight final segue obrigatório.
3. Relatórios do laboratório passam a registrar uma **fase predefinida e sanitizada** (`staging:source_archive`, `credentials`, `voicemail_pin_generation`, `dynamic_tenant`, `voicemail_validation`, `tls_certificate_generation`). Motivos específicos de geração/validação são mapeados para códigos seguros.
4. Regressões determinísticas em `scripts/tests/test_voicemail_pin_flake_postmortem.py` contemplam valores fracos, duplicados, sequenciais, limite de tentativas, integração de `prepare` sem Docker e proteção dos relatórios.

## Critério de aceite e pendências

Aprovada a CI completa no SHA da PR, a correção pode ser integrada na `main`, **sem mover a tag já criada `v0.1.0-rc.1`**. O próximo incidente terá informação de fase, mas nenhum PIN, senha SIP, configuração sensível ou mídia será impresso. Essa melhoria pode evitar a intermitência de geração de PIN; **não foi comprovado que ela foi a causa da tentativa original**.

A investigação de transporte SIP/TLS real, hardware de telefonia, 13 cenários de homologação e 15 provas operacionais permanece independente. **GO de produção: BLOQUEADO**.
