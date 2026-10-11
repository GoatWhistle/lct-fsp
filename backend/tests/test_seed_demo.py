"""Демо-засев: одна команда наполняет чистую базу через прод-сценарии, повторный запуск ничего не
дублирует, по демо-учёткам проходит вход — по паролю и через ФСП ID."""

from contextlib import closing

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, inspect, text

import fsp_stub
import seed_demo
from app.adapter.fsp_id import MemoryFspId
from app.adapter.password import Argon2Passwords
from app.domain.fsp import FspIdentity, FspIntent
from main import create_app
from settings import Mechanics, Settings
from tests.conftest import PASSWORD, Outbox
from validation.main import catalog


def rows(engine: Engine) -> dict[str, int]:
    with engine.connect() as conn:
        return {
            table: conn.execute(text(f'SELECT count(*) FROM "{table}"')).scalar_one()
            for table in sorted(inspect(engine).get_table_names())
            if table != "alembic_version"
        }


def test_seed_twice_gives_same_rows_and_demo_accounts_sign_in(
    db_engine: Engine, settings: Settings, mechanics: Mechanics, passwords: Argon2Passwords
) -> None:
    settings = settings.model_copy(update={"demo_mode": True})
    first = seed_demo.seed(settings, passwords=passwords)
    seeded = rows(db_engine)
    second = seed_demo.seed(settings, passwords=passwords)

    assert rows(db_engine) == seeded
    assert second == first
    grades = list(mechanics.grade_thresholds)
    assert {(code, grade, login is not None) for _, code, grade, login in first.candidates} == {
        (code, grade, fsp)
        for code in catalog().specializations
        for grade in grades
        for fsp in (False, True)
    }
    assert first.needs == sum(len(e.needs) for e in seed_demo.EMPLOYERS)

    fsp_id = MemoryFspId()
    app = create_app(settings, mechanics, passwords=passwords, fsp_id=fsp_id)
    with TestClient(app) as client:
        for email in [*first.employers, *(c[0] for c in first.candidates)]:
            signed = client.post(
                "/api/auth/login", json={"email": email, "password": seed_demo.DEMO_PASSWORD}
            )
            assert signed.status_code == 200, email

    users = {u["username"]: u for u in fsp_stub.generate()[0]["users"]}
    for email, _, _, login in first.candidates:
        if login is None:
            continue
        user = users[login]
        with closing(app.state.unit_of_work()) as uow:
            fsp = app.state.fsp_accounts(uow)
            started = fsp.start(FspIntent.login, None)
            state = started.authorization.state
            code = fsp_id.issue(FspIdentity(user["id"], user["email"], True), state)
            signed_in = fsp.complete(started.authorization, state=state, code=code, user=None)
        assert signed_in is not None
        assert signed_in.account.email == email
    app.state.engine.dispose()


def test_seed_refuses_without_explicit_demo_mode(
    db_engine: Engine, settings: Settings, passwords: Argon2Passwords
) -> None:
    before = rows(db_engine)

    with pytest.raises(seed_demo.DemoModeRequired):
        seed_demo.seed(settings, passwords=passwords)

    assert rows(db_engine) == before


def test_seed_keeps_real_users_untouched_and_never_deletes(
    db_engine: Engine, settings: Settings, passwords: Argon2Passwords, outbox: Outbox
) -> None:
    demo = settings.model_copy(update={"demo_mode": True})
    app = create_app(settings, mailer=outbox, passwords=passwords)
    with TestClient(app) as client:
        client.post(
            "/api/auth/register",
            json={"email": "real@example.com", "password": PASSWORD, "role": "employer"},
        ).raise_for_status()
    app.state.engine.dispose()
    with db_engine.connect() as conn:
        real = conn.execute(text("SELECT * FROM users WHERE email = 'real@example.com'")).one()

    seed_demo.seed(demo, passwords=passwords)
    seed_demo.seed(demo, passwords=passwords)

    with db_engine.connect() as conn:
        after = conn.execute(text("SELECT * FROM users WHERE email = 'real@example.com'")).one()
        demo_users = conn.execute(
            text("SELECT count(*) FROM users WHERE email LIKE '%@demo.example'")
        ).scalar_one()
        total = conn.execute(text("SELECT count(*) FROM users")).scalar_one()
    assert after == real
    assert total == demo_users + 1, "кроме демо-учёток и настоящей, в базе никого нет"


def test_seeded_accounts_have_no_password_login_outside_demo_mode(
    db_engine: Engine, settings: Settings, mechanics: Mechanics, passwords: Argon2Passwords
) -> None:
    seed_demo.seed(settings.model_copy(update={"demo_mode": True}), passwords=passwords)
    email = f"employer@{seed_demo.DOMAIN}"
    credentials = {"email": email, "password": seed_demo.DEMO_PASSWORD}

    closed = create_app(settings, mechanics, passwords=passwords)
    with TestClient(closed) as client:
        refused = client.post("/api/auth/login", json=credentials)
        assert refused.status_code == 401
        assert refused.json()["code"] == "invalid_credentials"
        assert "set-cookie" not in refused.headers
        assert client.get("/api/demo/status").json() == {"enabled": False}
        assert client.post("/api/demo/employer").status_code == 404
        assert client.post("/api/demo/candidate", json={}).status_code == 404
    closed.state.engine.dispose()

    opened = create_app(
        settings.model_copy(update={"demo_mode": True}), mechanics, passwords=passwords
    )
    with TestClient(opened) as client:
        assert client.post("/api/auth/login", json=credentials).status_code == 200
    opened.state.engine.dispose()
