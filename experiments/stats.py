"""集計用の統計関数（外部ライブラリなし）。"""

from __future__ import annotations

import math
import random


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """二項割合 k/n の95% Wilson信頼区間。"""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def binom_two_sided(k: int, n: int, p: float = 0.5) -> float:
    """正確な二項検定の両側p値（確率が観測値以下の結果の確率の合計）。"""
    if n == 0:
        return 1.0
    pmf = [math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(n + 1)]
    obs = pmf[k]
    return min(1.0, sum(x for x in pmf if x <= obs * (1 + 1e-9)))


def mcnemar_exact(b: int, c: int) -> float:
    """対応のある2値データの正確McNemar検定（不一致ペア b, c の二項検定）。"""
    return binom_two_sided(b, b + c)


def ece(pairs: list[tuple[float, bool]], n_bins: int) -> float:
    """期待較正誤差。pairs は (予測確率, 正解したか)。"""
    if not pairs:
        return float("nan")
    total = 0.0
    for i in range(n_bins):
        lo, hi = i / n_bins, (i + 1) / n_bins
        b = [(p, ok) for p, ok in pairs if lo <= p < hi or (i == n_bins - 1 and p == 1.0)]
        if b:
            acc = sum(ok for _, ok in b) / len(b)
            conf = sum(p for p, _ in b) / len(b)
            total += len(b) / len(pairs) * abs(acc - conf)
    return total


def bootstrap_mean_ci(xs: list[float], n_boot: int = 5000, seed: int = 0) -> tuple[float, float]:
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(n_boot))
    return means[int(0.025 * n_boot)], means[int(0.975 * n_boot) - 1]
