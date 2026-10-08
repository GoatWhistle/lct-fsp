"""Заглушка ФСП: realm Keycloak и реестр из одного детерминированного генератора."""

import json

import pytest

import fsp_stub
from app.adapter.catalog_file import load_catalog
from app.adapter.fsp_registry import FileFspRegistry
from app.domain.fsp import FspResult
from settings import CATALOG_FILE, FSP_REGISTRY_FILE


def test_generator_is_deterministic_and_subs_match_registry_keys() -> None:
    realm, registry = fsp_stub.generate()

    assert fsp_stub.generate() == (realm, registry)
    assert [u["id"] for u in realm["users"]] == list(registry)
    assert fsp_stub.generate(seed=fsp_stub.SEED + 1) != (realm, registry)


def test_committed_registry_and_realm_are_the_generator_output() -> None:
    realm, registry = fsp_stub.generate()

    assert FSP_REGISTRY_FILE.read_text(encoding="utf-8") == fsp_stub.dump(registry)
    if not fsp_stub.REALM_FILE.is_file():
        pytest.skip("realm export не смонтирован в контейнер тестов")
    assert json.loads(fsp_stub.REALM_FILE.read_text(encoding="utf-8")) == realm


def test_registry_uses_catalog_codes_and_covers_every_result_type() -> None:
    catalog = load_catalog(CATALOG_FILE)
    disciplines = {d.code for d in catalog.fsp_disciplines}
    roles = {s.code for s in catalog.specializations}
    _, registry = fsp_stub.generate()
    reader = FileFspRegistry(FSP_REGISTRY_FILE)

    found = [a for sub in registry for a in reader.achievements(sub)]

    assert {a.discipline for a in found} <= disciplines
    assert {a.team_role for a in found if a.team_role} <= roles
    assert {a.result for a in found} == set(FspResult)
    assert any(not achievements for achievements in registry.values())
    assert reader.achievements("неизвестный") == []
