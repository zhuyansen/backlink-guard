"""backlink-guard's flow as an animated SVG and a GIF: dots travel the connectors.

  python docs/make_diagram.py <zh|en> <out-basename> [--mark-new]

The 0.7 part: audit counts by referring site (a site-wide link counts once), and `lost` takes audit's backlink
data to the pages of yours that answer 404 or 410, each with a suggested 301 target from your sitemaps.

--mark-new highlights what 0.7 added: a line marked ★ is drawn in the highlight colour, a box whose title is
marked ★ gets the highlight border and a "NEW 0.7" tag, and a note under the commands says so; without it the
marks are dropped and everything is drawn plain.

rsvg-convert renders each frame (it does not run SVG animation) and ffmpeg joins them.
"""
import math, subprocess, sys, tempfile
from pathlib import Path

D = 136                                  # how far the lost row pushes everything from vet down
W, H = 760, 1180 + D
FONT = "Hiragino Sans GB, PingFang SC, Noto Sans CJK SC, sans-serif"
AMB = dict(fill="#FAECE7", stroke="#993C1D", title="#712B13", sub="#993C1D")
GRY = dict(fill="#F1EFE8", stroke="#5F5E5A", title="#444441", sub="#5F5E5A")
GRN = dict(fill="#E1F5EE", stroke="#0F6E56", title="#085041", sub="#0F6E56")
BLU = dict(fill="#E6F1FB", stroke="#185FA5", title="#0C447C", sub="#185FA5")
RED = dict(fill="#FCEBEB", stroke="#A32D2D", title="#791F1F", sub="#A32D2D")
YEL = dict(fill="#FAEEDA", stroke="#854F0B", title="#633806", sub="#854F0B")
CHIPS = (RED, YEL, BLU, GRY, GRN)        # skip, look first, free only, low value, submit
NEW = "#993C1D"                          # highlight for what 0.7 added

ZH = {
    "kw": ("你的关键词", "claude skills · ai seo tools"), "list": ("一份外链清单", "竞品缺口 · 付费榜 · Excel / CSV"),
    "me": ("你的域名", "看自己的外链画像"),
    "find": ("find：搜这个词的人落在哪", "Google 前 30 · 按访客排序", "榜单 · 导航站 · 文章 · 视频 · 社区 · 仓库"),
    "audit": ("audit：你自己的外链画像", "评分 · 每周新增和丢失 · 锚文本", "链你的站里谁的垃圾分高", "★ 按网站个数计 · 全站链接只算 1 个"),
    "lost": ("★ lost：外链落在 404 → 建议 301", "沿用 audit 的外链（AIsa 最多 1,000 条，缓存 7 天）",
             "只认 404 / 410 为死链 · 按引荐网站数排序", "301 目标取自你的 sitemap · 低于 0.50 不建议", "只给建议，不替你跳转"),
    "vet": ("vet：这个站值不值得发", "读页面就判 avoid 的，不再付费查"),
    "c1": ("读页面（免费）", "死站 · 停放 · 卖链接 · 要回链", "短链 · 站群模板 · 链向博彩", "收款链接（站群 / 被黑）· 共用统计账号"),
    "c2": ("GoAnyAPI", "评分 · 一年访问量 · 断崖", "还在不在收录里 · 注册日期", "访客来源（含 AI）· 自己的 write for us 页"),
    "c3": ("AIsa", "垃圾分 · 被 Google 打过没有", "页面成千上万、几乎没排名", "收款链接被多少个同类站共用"),
    "c4": ("可选", "--deep 徽章网络 · 未经证实 · Ahrefs 评分", "技术栈 · ChatGPT 提及 · 内页收款链接", "--recent 新页收录 · --topic 排名"),
    "c5": ("免费旁证", "Wayback 最早存档 · 过期域名被重新注册", "Google 知识图谱认不认识它"),
    "c6": ("本机记得的站群", "以往查过的页面模板、统计账号，记一年", "单独查一个站，也能认出同一个人的站群"),
    "c7": ("共享 spam 外链名单（GitHub）：名单上的站直接 avoid，不再付费查",),
    "avoid": ("avoid：别提交", "死站 · 停放 · 卖链接为业 · 短链", "收款链接站群 · 被黑注入"),
    "caution": ("caution：读证据再定", "两条以上问题才算", "卖链接 · 被 Google 打过 · 重注册"),
    "ok": ("ok：再看价值", "价值 高 / 中 / 低 / 无", "可附你的 GA 引荐访问数"),
    "action": ("建议：结论、政策风险、价值一起看", ("跳过", "先看看", "只免费提交", "价值低", "可以提交")),
    "report": ("举报站群", "名单上还没有的同一运营者站点", "附预填好的表单，你点提交才发出"),
    "new": "橙色字和「0.7 新增」标签 = 0.7 新增", "tag": "0.7 新增",
    "why": ("每条结论都附原文证据，和它对应的 Google 链接垃圾政策条款",
            "每行另附「政策风险」「价值」两栏 · 本可能查出问题的检查失败了：标「待定」，重跑"),
    "rules": ("提交规则", "只提交自己的 · 一周几个 · 锚文本换着用", "绝不买传权重的链接（付费要 sponsored / nofollow）"),
    "submit": ("你去提交", "工具不代你提交"), "verify": ("verify：上线后查链接", "在不在 · 传不传权重", "正文 / 页脚 / 侧栏 / 评论"),
    "log": ("log：提交账本", "一周超过 5 个提醒", "同一锚文本反复用提醒", "recheck：每月重查已上的站"),
    "use": ("命令行：backlink-guard  find · vet · verify · audit · lost · log · recheck",
            "Claude Code 插件 · Agent Skill：npx skills add zhuyansen/backlink-guard"),
    "legend": ("你给的输入", "检查", "数据来源", "结论：别发 / 小心 / 可以", "定期回看 · 举报回流"),
}
EN = {
    "kw": ("Your keywords", "claude skills · ai seo tools"), "list": ("A list of sites", "competitor gap · paid list · xlsx"),
    "me": ("Your domain", "your own link profile"),
    "find": ("find: where your searchers land", "Google's top 30 · by visitors", "lists · directories · articles · videos · threads"),
    "audit": ("audit: your own link profile", "rating · new and lost per week · anchors", "spammy sites linking to you",
              "★ Counted by referring site · site-wide counted once"),
    "lost": ("★ lost: backlinks landing on 404 → suggested 301", "audit's backlinks (AIsa, up to 1,000, cached 7 days)",
             "only 404 / 410 are dead · most referring sites first", "301 target from your sitemaps · none under 0.50",
             "a suggestion only: nothing is redirected"),
    "vet": ("vet: is this site worth it?", "settled by its own pages: no paid check"),
    "c1": ("Reading the pages (free)", "dead · parked · sells links · link back", "shortener · link network · gambling", "checkout links · shared analytics account"),
    "c2": ("GoAnyAPI", "rating · a year of visits · cliffs", "still indexed? · registration date", "visitor sources (AI too) · write-for-us"),
    "c3": ("AIsa", "spam score · hit by Google before?", "thousands of pages, no rankings", "how many look-alikes share its checkout"),
    "c4": ("Optional", "--deep badge network · unproven · Ahrefs", "tech · ChatGPT mentions · inner checkouts", "--recent new pages · --topic rank"),
    "c5": ("Free context", "Wayback first copy · re-registered domain", "known to Google's Knowledge Graph?"),
    "c6": ("Networks seen before", "templates and accounts from past checks", "one site alone still matches its network"),
    "c7": ("The shared spam-link list (GitHub): a listed site is avoid, no paid check",),
    "avoid": ("avoid: do not submit", "dead · parked · link seller", "checkout network · injected"),
    "caution": ("caution: read the evidence", "two findings or more", "sells links · hit by Google"),
    "ok": ("ok: then look at value", "value: high to none", "and what it sent you (GA)"),
    "action": ("Action: verdict, link policy and value read together", ("skip", "look first", "free only", "low value", "submit")),
    "report": ("Report a network", "sites the shared list lacks", "a filled-in form you submit"),
    "new": "orange text and the NEW 0.7 tag: new in 0.7", "tag": "NEW 0.7",
    "why": ("Each finding carries its evidence and the Google spam policy line it stands next to",
            "plus link policy and value columns · a check that failed: incomplete, run it again"),
    "rules": ("The rules", "your own project only · a few a week · vary the anchor", "never pay for a followed link (paid: sponsored or nofollow)"),
    "submit": ("You submit", "the tool never does"), "verify": ("verify: after it is live", "there? passing credit?", "in the text, or the footer?"),
    "log": ("log: your submissions", "over 5 a week: warned", "same anchor again: warned", "recheck them monthly"),
    "use": ("Command line: backlink-guard  find · vet · verify · audit · lost · log · recheck",
            "Claude Code plugin · Agent Skill: npx skills add zhuyansen/backlink-guard"),
    "legend": ("input", "checks", "data", "avoid / caution / ok", "look back · report back"),
}
VARIANTS = {"zh": ZH, "en": EN}


def width(text, size):
    return sum(size if ord(ch) > 0x2E7F else size * 0.6 for ch in text)


def new_tag(x, y, label):
    """The tag on the top border of a box that is new in 0.7, right-aligned at x."""
    tw = width(label, 10.5) + 14
    return (f'<rect x="{x - tw:.0f}" y="{y - 9}" width="{tw:.0f}" height="18" rx="9" fill="{NEW}"/>'
            f'<text x="{x - tw / 2:.0f}" y="{y + 4}" fill="#FFFFFF" font-weight="500" font-size="10.5">{label}</text>')


def box(x, y, w, h, c, lines, dashed=False, title_dy=0, size=14, tag=""):
    """A box: title over its lines. A ★ title gets the highlight border and the tag, a ★ line the highlight colour."""
    title, *subs = lines
    fresh = title.startswith("★ ")
    cx = x + w / 2
    dash = ' stroke-dasharray="5 3"' if dashed else ""
    stroke, sw = (NEW, 1.5) if fresh else (c["stroke"], 1 if dashed else 0.5)
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="{c["fill"]}" stroke="{stroke}" stroke-width="{sw}"{dash}/>']
    ty = y + h / 2 + 5 - 9 * len(subs) + title_dy
    out.append(f'<text x="{cx}" y="{ty}" fill="{c["title"]}" font-weight="500" font-size="{size}">{title.removeprefix("★ ")}</text>')
    for i, s in enumerate(subs):
        look = f'fill="{NEW}" font-weight="500"' if s.startswith("★ ") else f'fill="{c["sub"]}"'
        out.append(f'<text x="{cx}" y="{ty + 19 + 16.5 * i}" {look} font-size="12">{s.removeprefix("★ ")}</text>')
    if fresh and tag:
        out.append(new_tag(x + w - 12, y, tag))
    return "\n".join(out)


def action_bar(x, y, w, h, lines):
    """The action row: a title over one chip for each of the five actions, coloured as the verdicts are."""
    title, labels = lines
    cw = 124
    gap = (w - 32 - cw * len(labels)) / (len(labels) - 1)
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="#FFFFFF" stroke="{GRY["stroke"]}" stroke-width="0.5"/>',
           f'<text x="{x + w / 2}" y="{y + 20}" fill="{GRY["title"]}" font-weight="500" font-size="14">{title}</text>']
    for i, (label, c) in enumerate(zip(labels, CHIPS)):
        cx = x + 16 + i * (cw + gap)
        out.append(f'<rect x="{cx:.0f}" y="{y + 32}" width="{cw}" height="30" rx="4" fill="{c["fill"]}" stroke="{c["stroke"]}" stroke-width="0.5"/>')
        out.append(f'<text x="{cx + cw / 2:.0f}" y="{y + 52}" fill="{c["title"]}" font-weight="500" font-size="13">{label}</text>')
    return "\n".join(out)


# id, points, colour, dashed, dot duration (s), dot begin (s)
PATHS_06 = [
    ("k", [(140, 96), (140, 130)], "#888780", False, 1.0, 0.0),
    ("l", [(380, 96), (380, 240)], "#888780", False, 2.0, 0.4),
    ("d", [(620, 96), (620, 130)], "#888780", False, 1.0, 0.2),
    ("f", [(195, 204), (195, 240)], "#378ADD", False, 1.0, 0.6),
    ("v1", [(140, 622), (140, 652)], "#A32D2D", False, 1.0, 0.0),
    ("v2", [(380, 622), (380, 652)], "#854F0B", False, 1.0, 0.3),
    ("v3", [(620, 622), (620, 652)], "#0F6E56", False, 1.0, 0.6),
    ("a", [(690, 724), (690, 776)], "#378ADD", False, 1.0, 0.2),
    ("x", [(108, 850), (108, 882)], "#A32D2D", False, 1.0, 0.5),
    ("r", [(652, 850), (652, 882)], "#0F6E56", False, 1.0, 0.0),
    ("s", [(300, 948), (300, 965), (140, 965), (140, 982)], "#888780", False, 1.0, 0.5),
    ("t", [(250, 1022), (280, 1022)], "#888780", False, 0.8, 0.0),
    ("u", [(510, 1022), (540, 1022)], "#888780", False, 0.8, 0.4),
    ("loop", [(730, 1022), (748, 1022), (748, 167), (730, 167)], "#888780", True, 4.0, 0.0),
    ("loop2", [(730, 1022), (748, 1022), (748, 420), (730, 420)], "#888780", True, 4.0, 2.0),
    ("rep", [(30, 915), (14, 915), (14, 588), (46, 588)], "#A32D2D", True, 4.0, 1.0),
]
# the 0.6 layout from vet down moves by D; audit's backlink data feeds lost
PATHS = [(i, [(x, y + D if y >= 236 else y) for x, y in p], *rest) for i, p, *rest in PATHS_06]
PATHS.append(("lo", [(565, 220), (565, 248)], NEW, False, 1.0, 0.3))
DASH = ' stroke-dasharray="4 3"'


def scene(T):
    tag, Y = T.get("tag", ""), D
    boxes = "\n".join([
        box(30, 36, 220, 60, GRY, T["kw"]), box(270, 36, 220, 60, GRY, T["list"]), box(510, 36, 220, 60, GRY, T["me"]),
        box(30, 130, 330, 74, BLU, T["find"]), box(400, 130, 330, 90, BLU, T["audit"]),
        box(400, 248, 330, 104, BLU, T["lost"], title_dy=4, size=13, tag=tag),
        box(30, 240 + Y, 700, 382, BLU, T["vet"], title_dy=-169, size=15),
        box(46, 296 + Y, 326, 88, AMB, T["c1"]), box(388, 296 + Y, 326, 88, AMB, T["c2"]),
        box(46, 392 + Y, 326, 88, AMB, T["c3"]), box(388, 392 + Y, 326, 88, AMB, T["c4"], dashed=True),
        box(46, 488 + Y, 326, 72, AMB, T["c5"]), box(388, 488 + Y, 326, 72, AMB, T["c6"]),
        box(46, 568 + Y, 668, 40, AMB, T["c7"]),
        box(30, 652 + Y, 220, 72, RED, T["avoid"]), box(270, 652 + Y, 220, 72, YEL, T["caution"]), box(510, 652 + Y, 220, 72, GRN, T["ok"]),
        action_bar(30, 776 + Y, 700, 74, T["action"]),
        box(30, 882 + Y, 220, 66, RED, T["report"]), box(270, 882 + Y, 460, 66, GRY, T["rules"]),
        box(30, 982 + Y, 220, 80, GRY, T["submit"]), box(280, 982 + Y, 230, 80, BLU, T["verify"]), box(540, 982 + Y, 190, 80, BLU, T["log"]),
    ])
    lines = "\n".join(f'<path id="{i}" d="M{" L".join(f"{x} {y}" for x, y in p)}" fill="none" stroke="{c}" stroke-width="1"'
                      f'{DASH if dash else ""} marker-end="url(#arrow)"/>' for i, p, c, dash, *_ in PATHS)
    notes = ("".join(f'<text x="30" y="{744 + Y + 16 * i}" font-size="11" fill="#5F5E5A">{w}</text>' for i, w in enumerate(T["why"]) if w)
             + f'<path d="M30 {1080 + Y} H730" stroke="#D3D1C7" stroke-width="0.5" fill="none"/>'
             + "".join(f'<text x="380" y="{1100 + Y + 17 * i}" text-anchor="middle" font-size="11.5" fill="#5F5E5A">{u}</text>' for i, u in enumerate(T["use"]))
             + (f'<text x="380" y="{1134 + Y}" text-anchor="middle" font-size="11.5" fill="{NEW}">{T["new"]}</text>' if T.get("new") else ""))
    legend_y = 1150 + Y
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


def unstarred(T):
    """The labels with the ★ for what 0.7 added taken out, and no tag or line explaining it."""
    def clean(v):
        return tuple(clean(x) for x in v) if isinstance(v, tuple) else v.replace("★ ", "").replace("★", "")
    return {k: clean(v) for k, v in T.items() if k not in ("new", "tag")}


def main(variant, base, mark_new=False):
    T = VARIANTS[variant] if mark_new else unstarred(VARIANTS[variant])
    head, body = scene(T)
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
    main(sys.argv[1], sys.argv[2], "--mark-new" in sys.argv[3:])
