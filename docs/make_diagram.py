"""backlink-guard's flow as an animated SVG and a GIF: dots travel the connectors.

  python docs/make_diagram.py <zh|en> <out-basename>

rsvg-convert renders each frame (it does not run SVG animation) and ffmpeg joins them.
"""
import math, subprocess, sys, tempfile
from pathlib import Path

W, H = 760, 830
FONT = "Hiragino Sans GB, PingFang SC, Noto Sans CJK SC, sans-serif"
AMB = dict(fill="#FAECE7", stroke="#993C1D", title="#712B13", sub="#993C1D")
GRY = dict(fill="#F1EFE8", stroke="#5F5E5A", title="#444441", sub="#5F5E5A")
GRN = dict(fill="#E1F5EE", stroke="#0F6E56", title="#085041", sub="#0F6E56")
BLU = dict(fill="#E6F1FB", stroke="#185FA5", title="#0C447C", sub="#185FA5")
RED = dict(fill="#FCEBEB", stroke="#A32D2D", title="#791F1F", sub="#A32D2D")
YEL = dict(fill="#FAEEDA", stroke="#854F0B", title="#633806", sub="#854F0B")

ZH = {
    "kw": ("你的关键词", "claude skills · ai seo tools"), "list": ("一份外链清单", "竞品缺口 · 付费榜 · Excel / CSV"),
    "me": ("你的域名", "看自己的外链画像"),
    "find": ("find：搜这个词的人落在哪", "Google 前 30 · 按访客排序", "榜单 · 导航站 · 文章 · 视频 · 社区 · 仓库"),
    "audit": ("audit：你自己的外链画像", "评分 · 每周新增和丢失 · 锚文本", "链你的站里谁的垃圾分高"),
    "vet": ("vet：这个站值不值得发",),
    "c1": ("读页面（免费）", "死站 · 停放 · 卖链接 · 要回链", "短链 · 站群模板 · 链向博彩"),
    "c2": ("GoAnyAPI", "评分 · 一年访问量 · 断崖", "还在不在 Google 收录里"),
    "c3": ("AIsa（DataForSEO）", "垃圾分 · 被 Google 打过没有", "页面成千上万、几乎没排名"),
    "c4": ("可选", "--deep 徽章网络 · 未经证实", "--recent 新页收录 · --topic 排名"),
    "avoid": ("avoid：别提交", "死站 · 停放 · 卖链接为业 · 短链"), "caution": ("caution：读证据再定", "卖传权重链接 · 被 Google 打过"),
    "ok": ("ok：再看触达", "高 / 中 / 低"),
    "why": "每条结论都附原文证据，和它对应的 Google 链接垃圾政策条款",
    "rules": ("提交规则", "只提交自己的 · 一周几个 · 锚文本换着用 · 绝不买传权重的链接（付费要 sponsored / nofollow）"),
    "submit": ("你去提交", "工具不代你提交"), "verify": ("verify：上线后查链接", "在不在 · 传不传权重", "正文 / 页脚 / 侧栏 / 评论"),
    "log": ("log：提交账本", "一周超过 5 个提醒", "同一锚文本反复用提醒"),
    "use": ("命令行：python -m backlink_guard  find · vet · verify · audit · log", "Agent Skill：npx skills add zhuyansen/backlink-guard"),
    "legend": ("你给的输入", "检查", "数据来源", "结论：别发 / 小心 / 可以", "定期回看"),
}
EN = {
    "kw": ("Your keywords", "claude skills · ai seo tools"), "list": ("A list of sites", "competitor gap · paid list · xlsx"),
    "me": ("Your domain", "your own link profile"),
    "find": ("find: where your searchers land", "Google's top 30 · by visitors", "lists · directories · articles · videos · threads"),
    "audit": ("audit: your own link profile", "rating · new and lost per week · anchors", "spammy sites linking to you"),
    "vet": ("vet: is this site worth it?",),
    "c1": ("Reading the pages (free)", "dead · parked · sells links · link back", "shortener · link network · gambling"),
    "c2": ("GoAnyAPI", "rating · a year of visits · cliffs", "still listed by Google?"),
    "c3": ("AIsa (DataForSEO)", "spam score · hit by Google before?", "thousands of pages, no rankings"),
    "c4": ("Optional", "--deep badge networks · unproven", "--recent new pages · --topic rank"),
    "avoid": ("avoid: do not submit", "dead · parked · link seller"), "caution": ("caution: read the evidence", "sells followed links · hit by Google"),
    "ok": ("ok: then look at reach", "high / medium / low"),
    "why": "Each finding carries its evidence and the Google spam policy line it stands next to",
    "rules": ("The rules", "your own project only · a few a week · vary the anchor · never pay for a followed link"),
    "submit": ("You submit", "the tool never does"), "verify": ("verify: after it is live", "there? passing credit?", "in the text, or the footer?"),
    "log": ("log: your submissions", "over 5 a week: warned", "same anchor again: warned"),
    "use": ("Command line: python -m backlink_guard  find · vet · verify · audit · log", "Agent Skill: npx skills add zhuyansen/backlink-guard"),
    "legend": ("input", "checks", "data", "avoid / caution / ok", "look back"),
}
VARIANTS = {"zh": ZH, "en": EN}


def width(text, size):
    return sum(size if ord(ch) > 0x2E7F else size * 0.6 for ch in text)


def box(x, y, w, h, c, lines, dashed=False, title_dy=0, size=14):
    title, *subs = lines
    cx = x + w / 2
    dash = ' stroke-dasharray="5 3"' if dashed else ""
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="{c["fill"]}" stroke="{c["stroke"]}" stroke-width="{1 if dashed else 0.5}"{dash}/>']
    ty = y + h / 2 + 5 - 9 * len(subs) + title_dy
    out.append(f'<text x="{cx}" y="{ty}" fill="{c["title"]}" font-weight="500" font-size="{size}">{title}</text>')
    out += [f'<text x="{cx}" y="{ty + 19 + 16.5 * i}" fill="{c["sub"]}" font-size="12">{s}</text>' for i, s in enumerate(subs)]
    return "\n".join(out)


# id, points, colour, dashed, dot duration (s), dot begin (s)
PATHS = [
    ("k", [(140, 96), (140, 130)], "#888780", False, 1.0, 0.0),
    ("l", [(380, 96), (380, 240)], "#888780", False, 1.8, 0.4),
    ("d", [(620, 96), (620, 130)], "#888780", False, 1.0, 0.2),
    ("f", [(195, 204), (195, 240)], "#378ADD", False, 1.0, 0.6),
    ("v1", [(140, 446), (140, 478)], "#A32D2D", False, 1.0, 0.0),
    ("v2", [(380, 446), (380, 478)], "#854F0B", False, 1.0, 0.3),
    ("v3", [(620, 446), (620, 478)], "#0F6E56", False, 1.0, 0.6),
    ("r", [(660, 534), (660, 578)], "#0F6E56", False, 1.2, 0.2),
    ("s", [(140, 626), (140, 664)], "#888780", False, 1.0, 0.5),
    ("t", [(250, 694), (280, 694)], "#888780", False, 0.8, 0.0),
    ("u", [(510, 694), (540, 694)], "#888780", False, 0.8, 0.4),
    ("loop", [(730, 694), (748, 694), (748, 167), (730, 167)], "#888780", True, 4.0, 0.0),
]
DASH = ' stroke-dasharray="4 3"'


def scene(T):
    boxes = "\n".join([
        box(30, 36, 220, 60, GRY, T["kw"]), box(270, 36, 220, 60, GRY, T["list"]), box(510, 36, 220, 60, GRY, T["me"]),
        box(30, 130, 330, 74, BLU, T["find"]), box(400, 130, 330, 74, BLU, T["audit"]),
        box(30, 240, 700, 206, BLU, T["vet"], title_dy=-82, size=15),
        box(46, 284, 326, 72, AMB, T["c1"]), box(388, 284, 326, 72, AMB, T["c2"]),
        box(46, 364, 326, 72, AMB, T["c3"]), box(388, 364, 326, 72, AMB, T["c4"], dashed=True),
        box(30, 478, 220, 56, RED, T["avoid"]), box(270, 478, 220, 56, YEL, T["caution"]), box(510, 478, 220, 56, GRN, T["ok"]),
        box(30, 578, 700, 48, GRY, T["rules"]),
        box(30, 664, 220, 60, GRY, T["submit"]), box(280, 664, 230, 60, BLU, T["verify"]), box(540, 664, 190, 60, BLU, T["log"]),
    ])
    lines = "\n".join(f'<path id="{i}" d="M{" L".join(f"{x} {y}" for x, y in p)}" fill="none" stroke="{c}" stroke-width="1"'
                      f'{DASH if dash else ""} marker-end="url(#arrow)"/>' for i, p, c, dash, *_ in PATHS)
    notes = (f'<text x="30" y="560" font-size="11" fill="#5F5E5A">{T["why"]}</text>'
             f'<path d="M30 742 H730" stroke="#D3D1C7" stroke-width="0.5" fill="none"/>'
             + "".join(f'<text x="380" y="{762 + 17 * i}" text-anchor="middle" font-size="11.5" fill="#5F5E5A">{u}</text>' for i, u in enumerate(T["use"])))
    legend_y = 800
    swatches = [f'fill="{GRY["fill"]}" stroke="{GRY["stroke"]}" stroke-width="0.5"', f'fill="{BLU["fill"]}" stroke="{BLU["stroke"]}" stroke-width="0.5"',
                f'fill="{AMB["fill"]}" stroke="{AMB["stroke"]}" stroke-width="0.5"']
    labels = list(T["legend"])
    widths = [22 + width(labels[0], 12), 22 + width(labels[1], 12), 22 + width(labels[2], 12), 58 + width(labels[3], 12), 38 + width(labels[4], 12)]
    gap = (W - 60 - sum(widths)) / 4
    x, legend = 30, ""
    for i, (label, w) in enumerate(zip(labels, widths)):
        if i < 3:
            legend += f'<rect x="{x:.0f}" y="{legend_y}" width="14" height="14" rx="3" {swatches[i]}/>'
            legend += f'<text x="{x + 22:.0f}" y="{legend_y + 12}" font-size="12" fill="#444441">{label}</text>'
        elif i == 3:
            for k, c in enumerate((RED, YEL, GRN)):
                legend += f'<rect x="{x + 12 * k:.0f}" y="{legend_y}" width="10" height="14" rx="2" fill="{c["fill"]}" stroke="{c["stroke"]}" stroke-width="0.5"/>'
            legend += f'<text x="{x + 42:.0f}" y="{legend_y + 12}" font-size="12" fill="#444441">{label}</text>'
        else:
            legend += (f'<path d="M{x:.0f} {legend_y + 7} H{x + 30:.0f}" stroke="#888780" stroke-width="1" stroke-dasharray="4 3" fill="none"/>'
                       f'<text x="{x + 38:.0f}" y="{legend_y + 12}" font-size="12" fill="#444441">{label}</text>')
        x += w + gap
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W * 2}" height="{H * 2}" viewBox="0 0 {W} {H}" font-family="{FONT}">\n'
            '<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            '<path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></marker></defs>\n'
            f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>\n')
    return head, f'{lines}\n<g font-size="14" text-anchor="middle">\n{boxes}\n</g>\n{notes}\n{legend}\n'


def at(points, f):
    seg = [math.dist(a, b) for a, b in zip(points, points[1:])]
    left = f * sum(seg)
    for (a, b), s in zip(zip(points, points[1:]), seg):
        if left <= s:
            k = left / s if s else 0
            return a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k
        left -= s
    return points[-1]


def main(variant, base):
    head, body = scene(VARIANTS[variant])
    smil = "\n".join(f'<circle r="4" fill="{c}"><animateMotion dur="{dur}s" repeatCount="indefinite" begin="{b}s"><mpath href="#{i}"/></animateMotion></circle>'
                     for i, _, c, _, dur, b in PATHS)
    Path(base + ".svg").write_text(head + body + smil + "\n</svg>\n")
    fps, seconds = 15, 4.0
    with tempfile.TemporaryDirectory() as tmp:
        for n in range(int(fps * seconds)):
            tm = n / fps
            dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{c}"/>'
                           for _, p, c, _, dur, b in PATHS for x, y in [at(p, ((tm - b) % dur) / dur)])
            f = Path(tmp) / f"f{n:03d}.svg"
            f.write_text(head.replace("context-stroke", "#888780") + body + dots + "\n</svg>\n")
            subprocess.run(["rsvg-convert", "-w", str(W * 2), "-b", "white", str(f), "-o", str(f.with_suffix(".png"))], check=True)
        frames = ["-y", "-loglevel", "error", "-framerate", str(fps), "-i", f"{tmp}/f%03d.png"]
        subprocess.run(["ffmpeg", *frames, "-vf", "scale=1140:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=none",
                        base + ".gif"], check=True)
        subprocess.run(["cp", f"{tmp}/f030.png", base + ".png"], check=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
