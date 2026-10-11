"""Локальная модель в отдельных процессах для параллельных запросов стенда."""

from concurrent.futures import ProcessPoolExecutor

from app.adapter.text_model import Completion, ModelRequest

_completion: Completion | None = None


def _initialize(name: str, timeout: float) -> None:
    global _completion
    from composition import named_completion

    _completion = named_completion(name, timeout)


def _ask(request: ModelRequest) -> str:
    assert _completion is not None
    return _completion(request)


class IsolatedCompletion:
    """`Completion` поверх пула процессов с отдельным HTTP-клиентом в каждом."""

    def __init__(self, name: str, timeout: float, workers: int, model: str | None) -> None:
        self.model = model
        self._pool = ProcessPoolExecutor(
            workers,
            initializer=_initialize,
            initargs=(name, timeout),
        )

    def __call__(self, request: ModelRequest) -> str:
        return self._pool.submit(_ask, request).result()

    def close(self) -> None:
        self._pool.shutdown()
