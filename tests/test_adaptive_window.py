"""adaptive_asian_window_minutes 的阶梯扩窗单测。

2026-05-28 上线修复：原 daemon 注释写"widen up to 6h"，
实际只翻倍到 base*2 = 20 分钟，导致夏季赛事稀疏期长时间卡死。
现把逻辑抽到纯函数，按 streak 阶梯式扩窗到 360 分钟上限。
"""
from __future__ import annotations

import pytest

from football_data_mcp.sources import adaptive_asian_window_minutes


class TestAdaptiveAsianWindowMinutes:
    def test_low_streak_returns_base_window(self):
        for streak in (0, 1, 2):
            assert adaptive_asian_window_minutes(
                base_minutes=10, consecutive_empty_cycles=streak
            ) == 10

    def test_streak_3_to_5_doubles_window(self):
        for streak in (3, 4, 5):
            assert adaptive_asian_window_minutes(
                base_minutes=10, consecutive_empty_cycles=streak
            ) == 20

    def test_streak_6_to_8_quadruples_window(self):
        for streak in (6, 7, 8):
            assert adaptive_asian_window_minutes(
                base_minutes=10, consecutive_empty_cycles=streak
            ) == 40

    def test_streak_9_plus_uses_ceiling(self):
        for streak in (9, 50, 100):
            assert adaptive_asian_window_minutes(
                base_minutes=10, consecutive_empty_cycles=streak
            ) == 360

    def test_large_base_capped_at_360_when_amplified(self):
        # base 200，×2=400 应被压回 360；上限对放大有效。
        assert adaptive_asian_window_minutes(
            base_minutes=200, consecutive_empty_cycles=3
        ) == 360
        assert adaptive_asian_window_minutes(
            base_minutes=200, consecutive_empty_cycles=10
        ) == 360

    def test_user_explicit_large_base_is_respected(self):
        # 用户显式传 24h 基础窗口时，adaptive 不应把它压回 360；
        # 上限 360 只作用于"自动放大"出来的部分。
        for streak in (0, 1, 2, 3, 6, 9, 100):
            assert adaptive_asian_window_minutes(
                base_minutes=24 * 60, consecutive_empty_cycles=streak
            ) == 24 * 60

    def test_base_already_at_ceiling_stays_constant(self):
        for streak in (0, 5, 10):
            assert adaptive_asian_window_minutes(
                base_minutes=360, consecutive_empty_cycles=streak
            ) == 360

    def test_negative_streak_treated_as_zero(self):
        # 守护逻辑里 streak 不可能小于 0，但工具函数应当容错。
        assert adaptive_asian_window_minutes(
            base_minutes=10, consecutive_empty_cycles=-5
        ) == 10

    def test_none_streak_treated_as_zero(self):
        assert adaptive_asian_window_minutes(
            base_minutes=10, consecutive_empty_cycles=None  # type: ignore[arg-type]
        ) == 10

    def test_zero_or_negative_base_treated_as_one(self):
        # 容器配置异常时不应崩，最小回退到 1 分钟基窗。
        assert adaptive_asian_window_minutes(
            base_minutes=0, consecutive_empty_cycles=0
        ) == 1
        assert adaptive_asian_window_minutes(
            base_minutes=-30, consecutive_empty_cycles=0
        ) == 1

    @pytest.mark.parametrize(
        "base,streak,expected",
        [
            (180, 0, 180),
            (180, 3, 360),  # 180*2 = 360 命中上限
            (180, 9, 360),
            (60, 3, 120),
            (60, 6, 240),
            (60, 9, 360),
            # 用户显式大窗口：adaptive 不应缩小用户的基线设置。
            (720, 0, 720),
            (720, 3, 720),
            (720, 9, 720),
        ],
    )
    def test_known_combinations(self, base, streak, expected):
        assert adaptive_asian_window_minutes(
            base_minutes=base, consecutive_empty_cycles=streak
        ) == expected
