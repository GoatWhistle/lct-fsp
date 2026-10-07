"""Источники seed — реализации порта `SeedSource`: криптостойкий, фиксированный и производный
от seed прогона."""

import hashlib
import secrets
import threading

# Seed экземпляра хранится в BIGINT — неотрицательные значения влезают в 63 бита.
SEED_BITS = 63


class SecureSeeds:
    """Прод: по выданному seed никто не угадает следующее семейство и экземпляр."""

    def seed(self) -> int:
        return secrets.randbits(SEED_BITS)


class FixedSeeds:
    """Один и тот же seed на каждый запрос."""

    def __init__(self, value: int) -> None:
        if not 0 <= value < 2**SEED_BITS:
            raise ValueError(f"seed — от 0 до 2^{SEED_BITS}")
        self._value = value

    def seed(self) -> int:
        return self._value


class DerivedSeeds:
    """Последовательность seed, выведенная из seed прогона: n-й seed — хэш пары «прогон — n».
    Тот же seed прогона даёт ту же последовательность на любой машине. Номер берётся под
    блокировкой: запросы из пула потоков не получат один seed на двоих."""

    def __init__(self, run_seed: int) -> None:
        self._run_seed = run_seed
        self._issued = 0
        self._lock = threading.Lock()

    def seed(self) -> int:
        with self._lock:
            n, self._issued = self._issued, self._issued + 1
        digest = hashlib.sha256(f"{self._run_seed}:{n}".encode()).digest()
        return int.from_bytes(digest[:8]) >> (64 - SEED_BITS)
