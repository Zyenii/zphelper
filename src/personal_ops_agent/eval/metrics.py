from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RegressionStats:
    parse_attempts: int = 0
    parse_success: int = 0
    write_attempts: int = 0
    write_success: int = 0

    def snapshot(self) -> dict[str, float]:
        parse_rate = self.parse_success / self.parse_attempts if self.parse_attempts else 0.0
        write_rate = self.write_success / self.write_attempts if self.write_attempts else 0.0
        return {
            "parse_attempts": float(self.parse_attempts),
            "parse_success": float(self.parse_success),
            "parse_success_rate": parse_rate,
            "write_attempts": float(self.write_attempts),
            "write_success": float(self.write_success),
            "write_success_rate": write_rate,
        }


_STATS = RegressionStats()


def record_parse(success: bool) -> None:
    _STATS.parse_attempts += 1
    if success:
        _STATS.parse_success += 1


def record_write(success: bool) -> None:
    _STATS.write_attempts += 1
    if success:
        _STATS.write_success += 1


def get_regression_snapshot() -> dict[str, float]:
    return _STATS.snapshot()
