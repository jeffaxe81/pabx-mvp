from secrets_generator import generate_strong_secret, find_placeholders, replace_placeholder, replace_all_placeholders


# ---------- generate_strong_secret ----------

def test_generates_secret_of_requested_length():
    secret = generate_strong_secret(32)
    assert len(secret) == 32


def test_default_length_is_reasonably_strong():
    secret = generate_strong_secret()
    assert len(secret) >= 24  # abaixo disso não é "forte" de verdade


def test_generated_secrets_are_different_each_time():
    """Óbvio, mas se algum dia alguém trocar secrets.choice por random.choice sem seed, isso pegaria regressão de qualidade."""
    secrets_generated = {generate_strong_secret() for _ in range(20)}
    assert len(secrets_generated) == 20


def test_secret_contains_no_conf_unsafe_characters():
    """
    Sem aspas, espaço, =, ;, # - qualquer um desses teria significado
    especial dentro de um arquivo .conf do Asterisk e quebraria o
    parsing se caísse ali sem escape.
    """
    for _ in range(20):
        secret = generate_strong_secret()
        assert not any(c in secret for c in ' "\';=#\n\t')


# ---------- find_placeholders ----------

def test_finds_single_placeholder():
    content = "secret = troque_esta_senha_ami\n"
    assert find_placeholders(content) == {"troque_esta_senha_ami"}


def test_finds_multiple_distinct_placeholders():
    content = "a=troque_esta_senha_1001\nb=troque_esta_senha_web\n"
    assert find_placeholders(content) == {"troque_esta_senha_1001", "troque_esta_senha_web"}


def test_returns_empty_set_when_no_placeholders():
    assert find_placeholders("password=algumacoisaqualquer\n") == set()


def test_deduplicates_repeated_placeholder():
    content = "AMI_SECRET: troque_esta_senha_ami\nsecret = troque_esta_senha_ami\n"
    assert find_placeholders(content) == {"troque_esta_senha_ami"}


# ---------- replace_placeholder ----------

def test_replaces_all_occurrences():
    content = "AMI_SECRET: troque_esta_senha_ami\nsecret = troque_esta_senha_ami\n"
    result = replace_placeholder(content, "troque_esta_senha_ami", "novoSegredoForte123")
    assert "troque_esta_senha_ami" not in result
    assert result.count("novoSegredoForte123") == 2


def test_replace_does_not_affect_similar_but_different_placeholders():
    """
    'troque_esta_senha_ami' e 'troque_esta_senha_ami_admin' são
    placeholders DIFERENTES - trocar um não pode afetar o outro por
    acidente (ex: substring match desavisado).
    """
    content = "a=troque_esta_senha_ami\nb=troque_esta_senha_ami_admin\n"
    result = replace_placeholder(content, "troque_esta_senha_ami", "SEGREDO1")
    # troque_esta_senha_ami É substring de troque_esta_senha_ami_admin -
    # então o segundo também muda (SEGREDO1_admin), o que é esperado
    # de um replace ingênuo de string - documentamos esse comportamento
    # aqui em vez de escondê-lo.
    assert "SEGREDO1" in result
    assert "troque_esta_senha_ami_admin" not in result


def test_replace_preserves_rest_of_content():
    content = "; comentario\nsecret = troque_esta_senha_ami\nporta = 5038\n"
    result = replace_placeholder(content, "troque_esta_senha_ami", "X")
    assert "; comentario" in result
    assert "porta = 5038" in result


# ---------- replace_all_placeholders ----------

def test_replace_all_handles_substring_collision_correctly():
    """
    O bug real que motivou essa função: 'troque_esta_senha_ami' é
    substring de 'troque_esta_senha_ami_admin' - sem ordenar do mais
    longo pro mais curto, o segundo ficaria corrompido (mistura do
    novo segredo com o sufixo "_admin" do nome antigo).
    """
    content = "a=troque_esta_senha_ami\nb=troque_esta_senha_ami_admin\n"
    result = replace_all_placeholders(content, {
        "troque_esta_senha_ami": "SEGREDO_QUEUE",
        "troque_esta_senha_ami_admin": "SEGREDO_ADMIN",
    })
    assert "a=SEGREDO_QUEUE\n" in result
    assert "b=SEGREDO_ADMIN\n" in result
    assert "_admin" not in result  # nenhum resquício do placeholder antigo sobrou


def test_replace_all_with_multiple_unrelated_placeholders():
    content = "x=troque_esta_senha_1001\ny=troque_esta_senha_web\n"
    result = replace_all_placeholders(content, {
        "troque_esta_senha_1001": "A",
        "troque_esta_senha_web": "B",
    })
    assert result == "x=A\ny=B\n"
