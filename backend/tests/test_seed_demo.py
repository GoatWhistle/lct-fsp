"""Демо-засев: одна команда наполняет чистую базу через прод-сценарии, повторный запуск ничего не
дублирует, по демо-учёткам проходит вход — по паролю и через ФСП ID."""

from contextlib import closing

from fastapi.testclient import TestClient
from sqlalchemy import Engine, inspect, text

import fsp_stub
import seed_demo
from app.adapter.fsp_id import MemoryFspId
from app.adapter.password import Argon2Passwords
from app.domain.fsp import FspIdentity, FspIntent
from main import create_app
from settings import Mechanics, Settings
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
