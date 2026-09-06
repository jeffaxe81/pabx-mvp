from users import (
    load_users, save_users, validate_user_input, find_user,
    add_user, update_user, delete_user,
)

ADMIN_USER = {"username": "joao", "password": "senha-forte-123", "role": "admin"}
SUPERVISOR_USER = {"username": "maria", "password": "outra-senha-456", "role": "supervisor"}


def test_load_users_returns_empty_list_when_file_missing(tmp_path):
    assert load_users(tmp_path / "nao-existe.json") == []


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "users.json"
    add_user(path, ADMIN_USER)
    users = load_users(path)
    assert len(users) == 1
    assert users[0]["username"] == "joao"
    assert "password" not in users[0]  # só password_hash é persistido
    assert "password_hash" in users[0]


# ---------- validate_user_input ----------

def test_validate_accepts_correct_admin_input():
    ok, error, cleaned = validate_user_input(ADMIN_USER, existing=[])
    assert ok is True
    assert cleaned["username"] == "joao"
    assert cleaned["role"] == "admin"
    assert cleaned["password_hash"] != "senha-forte-123"  # nunca guarda em texto plano


def test_validate_rejects_invalid_username():
    ok, error, _ = validate_user_input({**ADMIN_USER, "username": "J!"}, existing=[])
    assert ok is False
    assert "usuário deve ter" in error


def test_validate_rejects_duplicate_username():
    ok, error, _ = validate_user_input(ADMIN_USER, existing=[{"username": "joao", "role": "admin", "password_hash": "x"}])
    assert ok is False
    assert "já existe" in error


def test_validate_rejects_invalid_role():
    ok, error, _ = validate_user_input({**ADMIN_USER, "role": "superadmin"}, existing=[])
    assert ok is False
    assert "papel inválido" in error


def test_validate_rejects_missing_password_for_new_user():
    data = {k: v for k, v in ADMIN_USER.items() if k != "password"}
    ok, error, _ = validate_user_input(data, existing=[])
    assert ok is False
    assert "senha obrigatória" in error


def test_validate_editing_keeps_old_hash_when_password_blank():
    existing = [{"username": "joao", "password_hash": "hash-antigo", "role": "admin"}]
    ok, error, cleaned = validate_user_input(
        {"username": "joao", "role": "supervisor", "password": ""}, existing, editing_username="joao"
    )
    assert ok is True
    assert cleaned["password_hash"] == "hash-antigo"
    assert cleaned["role"] == "supervisor"


def test_validate_editing_same_username_does_not_conflict_with_itself():
    existing = [{"username": "joao", "password_hash": "x", "role": "admin"}]
    ok, error, cleaned = validate_user_input(ADMIN_USER, existing, editing_username="joao")
    assert ok is True


# ---------- add / update / delete ----------

def test_add_user_persists_to_disk(tmp_path):
    path = tmp_path / "users.json"
    ok, error, cleaned = add_user(path, ADMIN_USER)
    assert ok is True
    assert find_user(load_users(path), "joao") is not None


def test_update_user_changes_role(tmp_path):
    path = tmp_path / "users.json"
    add_user(path, ADMIN_USER)

    ok, error, cleaned = update_user(path, "joao", {"role": "supervisor", "password": ""})
    assert ok is True
    assert cleaned["role"] == "supervisor"
    assert find_user(load_users(path), "joao")["role"] == "supervisor"


def test_update_user_rejects_unknown_username(tmp_path):
    path = tmp_path / "users.json"
    ok, error, cleaned = update_user(path, "nao-existe", {"role": "admin"})
    assert ok is False
    assert "não encontrado" in error


def test_delete_last_admin_is_blocked(tmp_path):
    path = tmp_path / "users.json"
    add_user(path, ADMIN_USER)

    ok, error = delete_user(path, "joao")
    assert ok is False
    assert "último" in error


def test_delete_non_last_admin_succeeds(tmp_path):
    path = tmp_path / "users.json"
    add_user(path, ADMIN_USER)
    add_user(path, {"username": "outro-admin", "password": "senha-outra-123", "role": "admin"})

    ok, error = delete_user(path, "joao")
    assert ok is True
    assert find_user(load_users(path), "joao") is None


def test_public_user_strips_password_hash():
    from users import public_user
    user = {"username": "joao", "password_hash": "abc123", "role": "admin"}
    result = public_user(user)
    assert "password_hash" not in result
    assert result["username"] == "joao"


def test_delete_user_rejects_unknown_username(tmp_path):
    path = tmp_path / "users.json"
    add_user(path, ADMIN_USER)
    ok, error = delete_user(path, "nao-existe")
    assert ok is False
    assert "não encontrado" in error
