"""note記事用の画像4枚を作る（APIは呼ばない）。

uv run python -m article.make_figures
→ article/images/fig1〜fig4.png, article/figures_data.md（元にした数値）

数値はログから計算し、results/summary.md の表記と一致することを確認してから描く。
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from experiments.common import ROOT, read_jsonl  # noqa: E402
from experiments.stats import ece, wilson  # noqa: E402
from game.engine import ACTIONS, Battle  # noqa: E402
from game.npcs import RuleNPC  # noqa: E402

OUT = ROOT / "article" / "images"
SUMMARY = (ROOT / "results" / "summary.md").read_text()

FONT_REG = "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"
FONT_BOLD = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
for f in (FONT_REG, FONT_BOLD):
    font_manager.fontManager.addfont(f)
JP = font_manager.FontProperties(fname=FONT_REG).get_name()
plt.rcParams.update({
    "font.family": JP,
    "font.size": 24,
    "axes.titlesize": 34,
    "axes.titleweight": "bold",
    "axes.labelsize": 26,
    "xtick.labelsize": 24,
    "ytick.labelsize": 26,
    "legend.fontsize": 22,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "savefig.facecolor": "white",
    "figure.facecolor": "white",
})

WIDTH_PX, DPI = 1280, 100
CREDIT = "Jev（jev-1.13.0）vs Decisions API（gpt-6-luna）／2026年10月 検証"

COLOR = {"jev": "#3fb8a6", "decisions": "#e39a3b", "rule": "#8c8c8c", "random": "#cfcfcf"}
LABEL = {"jev": "Jev", "decisions": "Decisions API", "rule": "if 文 NPC", "random": "ランダム"}
ACT_JA = {"attack": "こうげき", "power_attack": "ためこうげき", "defend": "ぼうぎょ",
          "potion": "かいふくやく", "flee": "にげる"}
ACT_COLOR = {"attack": "#c8553d", "power_attack": "#8e5ea2", "defend": "#3e7cb1",
             "potion": "#6aab5e", "flee": "#b5b5b5"}

DATA_LINES: list[str] = ["# 記事用画像の元データ", "",
                         "`article/make_figures.py` がログから計算した値。`results/summary.md` と一致を確認済み。", ""]


def check(text: str) -> None:
    """results/summary.md に同じ表記があることを確認する。"""
    if text not in SUMMARY:
        raise SystemExit(f"summary.md と一致しません: {text!r}")


def save(fig, name: str) -> None:
    fig.text(0.99, 0.012, CREDIT, ha="right", va="bottom", fontsize=15, color="#777777")
    path = OUT / name
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    w, h = Image.open(path).size
    assert w == WIDTH_PX, (name, w)
    print(f"{path.relative_to(ROOT)}: {w}x{h}")


# --- fig1 -----------------------------------------------------------------------

def bubble(draw: ImageDraw.ImageDraw, box, tail_to, lines, color, font_big, font_small) -> None:
    x0, y0, x1, y1 = box
    tx, ty = tail_to
    bx = (x0 + x1) / 2
    draw.polygon([(bx - 16, y1 - 4), (bx + 16, y1 - 4), (tx, ty)], fill="white", outline=color)
    draw.rounded_rectangle(box, radius=18, fill="white", outline=color, width=5)
    draw.line([(bx - 13, y1 - 1), (bx + 13, y1 - 1)], fill="white", width=6)  # 吹き出しと尻尾をつなぐ
    draw.line([(bx - 16, y1), (tx, ty)], fill=color, width=5)
    draw.line([(bx + 16, y1), (tx, ty)], fill=color, width=5)
    big, small = lines
    cy = y0 + 14
    for text, font in ((big, font_big), (small, font_small)):
        w = draw.textlength(text, font=font)
        draw.text(((x0 + x1 - w) / 2, cy), text, font=font, fill="#1b1b1b")
        cy += font.size + 10


def fig1() -> None:
    src = Image.open(ROOT / "replay" / "screenshots" / "01_hesitating.png").convert("RGB")
    src = src.crop((0, 0, src.width, 845))  # 下の余白を除く（元画像は変更しない）
    s = WIDTH_PX / src.width
    img = src.resize((WIDTH_PX, round(src.height * s)), Image.LANCZOS)
    footer = 56
    canvas = Image.new("RGB", (WIDTH_PX, img.height + footer), "white")
    canvas.paste(img, (0, 0))
    d = ImageDraw.Draw(canvas)
    fb = ImageFont.truetype(FONT_BOLD, 34)
    fs = ImageFont.truetype(FONT_BOLD, 20)
    S = lambda *xy: tuple(round(v * s) for v in xy)  # noqa: E731  元画像の座標 → 出力の座標
    # Jev：心の声の confidence 0.19 を指す
    bubble(d, S(20, 396, 182, 478), S(300, 550), ("迷い中…", "（confidence 0.19）"),
           COLOR["jev"], fb, fs)
    # Decisions：選んだ「こうげき 90%」を指す
    bubble(d, S(446, 396, 598, 478), S(500, 572), ("即決！", "（こうげき 90%）"),
           COLOR["decisions"], fb, fs)
    fc = ImageFont.truetype(FONT_REG, 20)
    w = d.textlength(CREDIT, font=fc)
    d.text((WIDTH_PX - w - 16, img.height + (footer - 20) / 2), CREDIT, font=fc, fill="#777777")
    path = OUT / "fig1_screen_annotated.png"
    canvas.save(path)
    print(f"{path.relative_to(ROOT)}: {canvas.width}x{canvas.height}")


# --- fig2 -----------------------------------------------------------------------

def fig2() -> None:
    rows = read_jsonl(ROOT / "logs" / "tournament.jsonl")
    npcs = ["jev", "decisions", "rule", "random"]
    pct = {}
    for n in npcs:
        c = Counter(r["choice"] for r in rows if r["actor"] == n and not r.get("forced"))
        tot = sum(c.values())
        pct[n] = {a: 100 * c[a] / tot for a in ACTIONS}
        pct[n]["_n"] = tot
    for a in ACTIONS:
        check(f"| {a} | " + " | ".join(f"{pct[n][a]:.1f}%" for n in npcs) + " |")

    DATA_LINES.extend(["## fig2 行動の内訳（全対戦、自分で選んだ行動のみ）", "",
                       "| NPC | 選択回数 | " + " | ".join(ACT_JA[a] for a in ACTIONS) + " |",
                       "| --- | --- |" + " --- |" * len(ACTIONS)])
    for n in npcs:
        DATA_LINES.append(f"| {LABEL[n]} | {pct[n]['_n']} | " +
                          " | ".join(f"{pct[n][a]:.1f}%" for a in ACTIONS) + " |")
    DATA_LINES.append("")

    fig, ax = plt.subplots(figsize=(WIDTH_PX / DPI, 7.6))
    fig.subplots_adjust(left=0.22, right=0.95, top=0.74, bottom=0.12)
    ys = list(range(len(npcs)))[::-1]
    for y, n in zip(ys, npcs):
        left = 0.0
        for a in ACTIONS:
            v = pct[n][a]
            ax.barh(y, v, left=left, color=ACT_COLOR[a], edgecolor="white", linewidth=2, height=0.68)
            if v >= 7:
                ax.text(left + v / 2, y, f"{v:.0f}%", ha="center", va="center", color="white",
                        fontsize=22, fontweight="bold")
            left += v
    ax.set_yticks(ys, [LABEL[n] for n in npcs])
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=ACT_COLOR[a]) for a in ACTIONS]
    fig.legend(handles, [ACT_JA[a] for a in ACTIONS], loc="upper center", ncol=5,
               bbox_to_anchor=(0.5, 0.86), frameon=False, handlelength=0.9, columnspacing=0.9,
               handletextpad=0.4)
    fig.suptitle("戦い方の違い：行動の内訳", x=0.5, y=0.965, fontsize=34, fontweight="bold")
    save(fig, "fig2_action_mix.png")


# --- fig3 -----------------------------------------------------------------------

def fig3() -> None:
    rows = read_jsonl(ROOT / "logs" / "positions_api.jsonl")
    positions = read_jsonl(ROOT / "data" / "positions.jsonl")
    clear = [p for p in positions if p["label"] == "clear"]
    acc = {}
    for a in ("jev", "decisions"):
        rs = [r for r in rows if r["actor"] == a and r["label"] == "clear"]
        k = sum(r["choice"] == r["answer"] for r in rs)
        lo, hi = wilson(k, len(rs))
        acc[a] = (k, len(rs), 100 * k / len(rs), 100 * lo, 100 * hi)
        check(f"| {a} | {k}/{len(rs)} = {100 * k / len(rs):.1f}%（{100 * lo:.1f}〜{100 * hi:.1f}） |")
    k = sum(RuleNPC().act(Battle.from_state(p["game_state"], seed=0), "left") == p["answer"] for p in clear)
    lo, hi = wilson(k, len(clear))
    acc["rule"] = (k, len(clear), 100 * k / len(clear), 100 * lo, 100 * hi)
    check(f"| Rule NPC（if文） | {k}/{len(clear)} = {100 * k / len(clear):.1f}%")
    rnd = 100 * sum(1 / len(p["available"]) for p in clear) / len(clear)
    acc["random"] = (None, None, rnd, None, None)
    check(f"| ランダムに選んだ場合の期待値 | {rnd:.1f}% |")

    DATA_LINES.extend(["## fig3 正答率（正解あり 100 局面）", "",
                       "| 方法 | 正解数 | 正答率 | 95% 信頼区間 |", "| --- | --- | --- | --- |"])
    for n in ("rule", "decisions", "jev", "random"):
        k, nn, v, lo, hi = acc[n]
        DATA_LINES.append(f"| {LABEL[n] if n != 'random' else 'ランダム（期待値）'} | "
                          f"{f'{k}/{nn}' if k is not None else '—'} | {v:.1f}% | "
                          f"{f'{lo:.1f}〜{hi:.1f}%' if lo is not None else '—'} |")
    DATA_LINES.extend(["", "Jev・Decisions API は 100 局面 × 選択肢の順番 5 通り = 500 回。"
                       "if 文 NPC は順番に依存しないため 100 局面。", ""])

    order = ["rule", "decisions", "jev", "random"]
    names = {"rule": "if 文 NPC", "decisions": "Decisions API", "jev": "Jev", "random": "ランダム（期待値）"}
    fig, ax = plt.subplots(figsize=(WIDTH_PX / DPI, 7.4))
    fig.subplots_adjust(left=0.27, right=0.95, top=0.85, bottom=0.25)
    ys = list(range(len(order)))[::-1]
    for y, n in zip(ys, order):
        k, nn, v, lo, hi = acc[n]
        kw = dict(color=COLOR[n], height=0.62)
        if n == "rule":
            kw.update(color="white", edgecolor=COLOR["rule"], hatch="//", linewidth=2.5)
        ax.barh(y, v, **kw)
        label_x = v + 1.5
        if n in ("jev", "decisions"):
            ax.errorbar(v, y, xerr=[[v - lo], [hi - v]], fmt="none", ecolor="#333333",
                        elinewidth=2.5, capsize=10, capthick=2.5)
            label_x = hi + 1.5
        ax.text(label_x, y, f"{v:.0f}%" if n == "rule" else f"{v:.1f}%", va="center",
                fontsize=26, fontweight="bold")
    ax.set_yticks(ys, [names[n] for n in order])
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_title("1 手ごとの判断の正答率", pad=24)
    fig.text(0.04, 0.115, "※ if 文 NPC は正解の計算に使った戦い方と同じ系統のため参考値", fontsize=20, color="#444444")
    fig.text(0.04, 0.065, "正解あり 100 局面。エラーバーは 95% 信頼区間", fontsize=18, color="#666666")
    save(fig, "fig3_accuracy.png")


# --- fig4 -----------------------------------------------------------------------

def fig4() -> None:
    rows = read_jsonl(ROOT / "logs" / "positions_api.jsonl")
    pts, eces = {}, {}
    DATA_LINES.extend(["## fig4 較正（正解あり 500 回、選んだ行動につけた確率で 0.2 刻み）", "",
                       "| API | 区間 | 件数 | 平均確率 | 正答率 | 図に使用 |", "| --- | --- | --- | --- | --- | --- |"])
    for a in ("jev", "decisions"):
        rs = [r for r in rows if r["actor"] == a and r["label"] == "clear" and r["probabilities"]]
        pairs = [(r["probabilities"].get(r["choice"], 0.0), r["choice"] == r["answer"]) for r in rs]
        eces[a] = ece(pairs, 5)
        pts[a] = []
        for i in range(5):
            lo, hi = i / 5, (i + 1) / 5
            b = [(p, ok) for p, ok in pairs if lo <= p < hi or (i == 4 and p == 1.0)]
            if not b:
                continue
            mp, accv = sum(p for p, _ in b) / len(b), sum(ok for _, ok in b) / len(b)
            check(f"{len(b)} | {mp:.2f} | {100 * accv:.1f}%")
            used = len(b) >= 10
            DATA_LINES.append(f"| {LABEL[a]} | {lo:.1f}〜{hi:.1f} | {len(b)} | {mp:.2f} | {100 * accv:.1f}% | "
                              f"{'○' if used else '×（10 件未満）'} |")
            if used:
                pts[a].append((mp, accv, len(b)))
    check("| ECE（5区間） | " + " | ".join(f"{eces[a]:.3f}" for a in ("jev", "decisions")) + " |")
    DATA_LINES.extend(["", f"ECE（5 区間）：Jev {eces['jev']:.3f}、Decisions API {eces['decisions']:.3f}", ""])

    fig, ax = plt.subplots(figsize=(WIDTH_PX / DPI, 10.4))
    fig.subplots_adjust(left=0.14, right=0.95, top=0.88, bottom=0.2)
    ax.plot([0, 1], [0, 1], ls=":", color="#888888", lw=2.5)
    ax.text(0.24, 0.12, "理想（言ったとおりに当たる）", ha="left", va="center",
            fontsize=21, color="#666666")
    legend = {"jev": f"Jev（ずれ 約 {eces['jev'] * 100:.0f} ポイント）",
              "decisions": f"Decisions API（ずれ 約 {eces['decisions'] * 100:.0f} ポイント）"}
    for a in ("jev", "decisions"):
        xs, ys, ns = zip(*pts[a])
        ax.plot(xs, ys, color=COLOR[a], lw=4, zorder=2, label=legend[a])
        ax.scatter(xs, ys, s=[n * 6 + 80 for n in ns], color=COLOR[a], edgecolor="white",
                   linewidth=2, zorder=3)
        for x, y, n in zip(xs, ys, ns):
            if a == "jev":
                ax.text(x - 0.035, y + 0.02, f"{n} 件", ha="right", va="center", fontsize=17, color="#555555")
            else:
                dx, ha = (0.0, "center") if x > 0.85 else (0.03, "left")
                ax.text(x + dx, y - 0.075, f"{n} 件", ha=ha, va="center", fontsize=17, color="#555555")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.08)
    ticks = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
    ax.set_xticks(ticks, [f"{t:.1f}" for t in ticks])
    ax.set_yticks(ticks, [f"{t:.1f}" for t in ticks])
    ax.set_xlabel("AI が選んだ行動につけた確率", labelpad=12)
    ax.set_ylabel("実際の正答率", labelpad=12)
    ax.grid(color="#eeeeee", lw=1.2)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left", frameon=False, handlelength=1.6)
    ax.set_title("AI の『自信』は当たるのか", pad=24)
    fig.text(0.04, 0.05, "正解あり 100 局面 × 5 順序。0.2 刻みで集計し、10 件未満の区間は除外。点の大きさは件数",
             fontsize=16, color="#666666")
    save(fig, "fig4_calibration.png")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig1()
    fig2()
    fig3()
    fig4()
    (ROOT / "article" / "figures_data.md").write_text("\n".join(DATA_LINES) + "\n")


if __name__ == "__main__":
    main()
