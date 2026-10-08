"""M21 на стенде валидации: разбор потребности тем же сценарием, что HTTP, точность по полям на
размеченном наборе и таблица отчёта (docs/validation-plan.md, M21)."""

import json
import socket
from pathlib import Path

import pytest

from app.adapter.text_model import ModelRequest
from app.domain.catalog import CatalogRef
from app.domain.need_draft import CheckedDraft, CheckedOutOfCatalog
from app.domain.work import WorkFormat
from composition import model_understanding
from settings import BACKEND_DIR, Mechanics, Settings
from tests.text_model_contract import SYNONYMS, answer
from validation import commands
from validation.commands import _Capture, recording_path, report_parsing
from validation.main import build_stand
from validation.parsing import LabeledText, load_labeled, score_parsing, typical_errors
from validation.recorded import Answer, Recording, Replay, record, request_key

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


def _brain(request: ModelRequest) -> str:
    """«Модель» стенда: QA, если в тексте есть pytest, иначе ничего не узнала."""
    found = "pytest" in request.user.lower()
    return json.dumps(answer(specialization="qa" if found else None))


def _recorded(tmp_path: Path, ms: float = 5.0, error: str | None = None) -> Path:
    """Запись ответов на фикстуру, как её делает `--record`, — с заданным временем ответа."""
    texts = load_labeled(FIXTURE)
    capture = _Capture()
    stand = build_stand(MECHANICS, understanding=model_understanding(capture, SYNONYMS, timeout=5))
    for t in texts:
        stand.need_drafts().parse(t.text)
    recording = Recording(recording_path(FIXTURE, "fake"))
    for request in capture.requests:
        raw = None if error else _brain(request)
        recording.add(request_key(request), Answer(raw, error, ms))
    recording.model = "fake-1"
    recording.save()
    return recording.path


@pytest.fixture
def recorded_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(commands, "RECORDED_DIR", tmp_path)
    return tmp_path


def test_record_asks_model_only_for_missing_answers(recorded_dir: Path) -> None:
    asked: list[ModelRequest] = []

    def live(request: ModelRequest) -> str:
        asked.append(request)
        return _brain(request)

    requests = [ModelRequest("s", "pytest", {}), ModelRequest("s", "1С", {})]
    recording = Recording(recorded_dir / "r.json")

    assert record(recording, requests, live, workers=2, model="fake-1") == 2
    assert record(Recording(recorded_dir / "r.json"), requests, live, workers=2, model=None) == 0
    assert len(asked) == 2
    assert Recording(recorded_dir / "r.json").model == "fake-1"


def test_model_report_rebuilds_from_recording_without_network(
    recorded_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _recorded(recorded_dir, ms=1234.0)

    def refuse(*_: object, **__: object) -> None:
        raise AssertionError("отчёт пошёл в сеть")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)

    report_parsing(MECHANICS, FIXTURE, "fake", timeout=10)

    out = capsys.readouterr().out
    assert "модель fake-1 из записи need_texts.fake.json" in out
    assert "откат на правила — 0 из" in out
    assert "| Специализация" in out
    # Время разбора — записанное время модели, а не мгновенный повтор.
    assert "Медиана времени разбора: 123" in out


def test_recorded_answer_slower_than_timeout_falls_back_to_rules(
    recorded_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _recorded(recorded_dir, ms=20_000.0)
    total = len(load_labeled(FIXTURE))

    report_parsing(MECHANICS, FIXTURE, "fake", timeout=10)

    out = capsys.readouterr().out
    assert f"откат на правила — {total} из {total}" in out
    assert "Медиана времени разбора: 100" in out


def test_recorded_model_error_falls_back_to_rules(recorded_dir: Path) -> None:
    _recorded(recorded_dir, error="нет ответа")
    replay = Replay(Recording(recording_path(FIXTURE, "fake")), timeout=10)
    understanding = model_understanding(replay, SYNONYMS, timeout=10)
    drafts = build_stand(MECHANICS, understanding=understanding).need_drafts()
    rules = build_stand(MECHANICS).need_drafts()
    text = load_labeled(FIXTURE)[0].text

    assert drafts.parse(text) == rules.parse(text)
    assert replay.failed == 1


def test_incomplete_recording_stops_report(recorded_dir: Path) -> None:
    path = _recorded(recorded_dir)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["answers"].pop(next(iter(data["answers"])))
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(SystemExit, match="нет ответов на 1 текстов"):
        report_parsing(MECHANICS, FIXTURE, "fake")


def test_recording_holds_one_model(recorded_dir: Path) -> None:
    recording = Recording(recorded_dir / "r.json")
    record(recording, [ModelRequest("s", "a", {})], _brain, workers=1, model="fake-1")

    with pytest.raises(ValueError, match="fake-1"):
        record(recording, [ModelRequest("s", "b", {})], _brain, workers=1, model="fake-2")


def test_model_report_without_recording_explains(recorded_dir: Path) -> None:
    with pytest.raises(SystemExit, match="--record"):
        report_parsing(MECHANICS, FIXTURE, "fake")


def test_typical_errors_count_misses_by_field() -> None:
    texts = [
        labeled(specialization="qa", grade="middle", stack=["pytest"]),
        labeled(specialization="qa", grade="middle", stack=["pytest"], salary_from=100),
        labeled(out_of_catalog=True),
    ]
    parsed: list[CheckedDraft | CheckedOutOfCatalog] = [
        draft(specialization=ref("backend"), grade=ref("middle"), stack=(ref("java"),)),
        draft(specialization=ref("backend"), grade=ref("middle")),
        draft(specialization=ref("backend")),
    ]

    errors = typical_errors(texts, parsed)

    assert errors["specialization"] == [("qa → backend", 2)]
    assert "grade" not in errors
    assert errors["stack"] == [("пропущен pytest", 2), ("лишний java", 1)]
    assert errors["salary"] == [("нет вилки", 1)]
    assert errors["out_of_catalog"] == [("вне справочника → backend", 1)]
