"""M21 на стенде валидации: разбор потребности тем же сценарием, что HTTP, точность по полям на
размеченном наборе и таблица отчёта (docs/validation-plan.md, M21)."""

import socket

import pytest

from app.domain.catalog import CatalogRef
from app.domain.need_draft import CheckedDraft, CheckedOutOfCatalog
from app.domain.work import WorkFormat
from settings import BACKEND_DIR, Mechanics, Settings
from validation.commands import report_parsing
from validation.main import build_stand
from validation.parsing import LabeledText, load_labeled, score_parsing

MECHANICS = Mechanics.from_yaml(Settings().mechanics_file)
FIXTURE = BACKEND_DIR / "tests" / "data" / "need_texts.yaml"


def labeled(**fields: object) -> LabeledText:
    base: dict[str, object] = {
        "id": "x",
        "source": "пример",
        "date": "2026-10-08",
        "checked_by": "команда",
        "text": "",
    }
    return LabeledText.model_validate(base | fields)


def draft(**fields: object) -> CheckedDraft:
    base: dict[str, object] = {
        "title": None,
        "specialization": None,
        "grade": None,
        "stack": (),
        "work_format": None,
        "city": None,
        "salary_from": None,
        "salary_to": None,
        "confidence": {},
        "uncertain": frozenset(),
    }
    return CheckedDraft(**(base | fields))  # type: ignore[arg-type]


def ref(code: str) -> CatalogRef:
    return CatalogRef(code, code)


def test_field_accuracy_counts_out_of_catalog_answer_as_miss() -> None:
    texts = [
        labeled(specialization="qa", grade="middle", stack=["pytest", "postman"]),
        labeled(specialization="qa", grade="junior", stack=["pytest"], salary_to=300_000),
        labeled(specialization="backend", grade="middle", work_format="remote"),
        labeled(out_of_catalog=True),
        labeled(out_of_catalog=True),
    ]
    parsed: list[CheckedDraft | CheckedOutOfCatalog] = [
        draft(specialization=ref("qa"), grade=ref("middle"), stack=(ref("pytest"), ref("java"))),
        draft(specialization=ref("qa"), stack=(ref("pytest"),), salary_to=300_000),
        CheckedOutOfCatalog("1С", (ref("backend"),)),
        CheckedOutOfCatalog("1С", (ref("backend"),)),
        draft(specialization=ref("backend")),
    ]

    scores = {s.field: s for s in score_parsing(texts, parsed)}

    assert scores["specialization"].value == pytest.approx(2 / 3)
    assert scores["specialization"].baseline == pytest.approx(2 / 3)
    assert scores["grade"].value == pytest.approx(1 / 3)
    # TP 2 (pytest дважды), FP 1 (java), FN 1 (postman).
    assert scores["stack"].value == pytest.approx(2 * 2 / (2 * 2 + 1 + 1))
    assert scores["work_format"].value == pytest.approx(2 / 3)
    assert (scores["salary"].total, scores["salary"].value) == (1, 1.0)
    assert scores["out_of_catalog"].value == pytest.approx(1 / 2)
    assert scores["out_of_catalog"].passed is False


def test_fixture_follows_dataset_format() -> None:
    texts = load_labeled(FIXTURE)

    assert len(texts) >= 5
    assert any(t.out_of_catalog for t in texts)
    assert all(t.checked_by and t.source for t in texts)
    assert {t.work_format for t in texts} >= {WorkFormat.office, WorkFormat.remote}


def test_parsing_command_prints_m21_table(capsys: pytest.CaptureFixture[str]) -> None:
    report_parsing(MECHANICS, FIXTURE)

    out = capsys.readouterr().out
    assert "M21" in out
    for field in ("Специализация", "Грейд", "Стек, micro-F1", "Формат", "Город", "Вилка"):
        assert f"| {field}" in out
    assert "| Вне справочника, полнота | 1 | 1.00 |" in out
    assert "Медиана времени разбора" in out


def test_parsing_command_without_dataset_explains_format() -> None:
    with pytest.raises(SystemExit, match=r"need_texts\.md"):
        report_parsing(MECHANICS, BACKEND_DIR / "validation" / "data" / "absent.yaml")


def test_stand_parsing_makes_no_network_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Сценарий разбора со справочником и проверкой вывода — без единого сетевого вызова."""
    drafts = build_stand(MECHANICS).need_drafts()

    def refuse(*_: object, **__: object) -> None:
        raise AssertionError("разбор пошёл в сеть")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)

    parsed = drafts.parse("Middle QA-инженер, pytest, удалённо, Москва, 200–250 тыс.")

    assert isinstance(parsed, CheckedDraft)
    assert parsed.specialization == CatalogRef("qa", "QA")
