# -*- coding: utf-8 -*-
"""生成"纸上推演"表格的 Word 文档（不依赖任何第三方库）。

用法:
    python 生成推演表.py

为什么手写 docx：python-docx 没装，而 .docx 本质是个 zip + XML。
自己拼一份最小可用的，比装依赖快，而且以后想改格式直接改这里。
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "1014推演表.docx"

# --------------------------------------------------------------------------
# 内容定义：改这里就能改文档
# --------------------------------------------------------------------------
TITLE = "文章翻译审校 · 状态推演表"
INTRO = [
    "用法：照着你的设计图（1013设计图.docx），把每一轮 state 里 5 个字段的值填出来。",
    "场景：一篇中文文章进来，第一次翻译就没通过，一路改到底。",
    "填法：把每一格该是什么值写进去。不知道就写“?”，再回去想。",
]

COLUMNS = ["步骤", "source_text", "translation", "approved", "round", "review_feedback", "router 判断"]

ROWS = [
    ["① 入口（刚进来）", "中文原文", "空字符串 \"\"", "False", "", "\"\"", "—"],
    ["② translate 跑完", "同上", "英文第1稿", "False", "", "\"\"", "—"],
    ["③ review 跑完（不通过）", "同上", "同上", "", "同上", "", "—"],
    ["④ router 判断 → 去哪？", "", "", "", "", "", ""],
    ["⑤ translate 第2次跑完", "同上", "", "同上", "", "同上", "—"],
    ["⑥ review 第2次（又不通过）", "同上", "同上", "False", "同上", "\"再改\"", "—"],
    ["⑦ router → 去哪？", "", "", "", "", "", ""],
    ["⑧ translate 第3次跑完", "同上", "英文第3稿", "同上", "", "同上", "—"],
    ["⑨ review 第3次（还是不通过）", "同上", "同上", "", "同上", "\"还不行\"", "—"],
    ["⑩ router → 去哪？为什么？", "", "", "", "", "", ""],
]

NOTES_TITLE = "三个关键点（填的时候要卡准）"
NOTES = [
    "① round 从哪里开始？0 还是 1？—— 这决定“最多重译 3 次”到底是翻译几次，先想清楚再填。",
    "② 第 ⑨ 步：审核还是不通过，但 round 已经到 3 了，router 怎么判？"
    "你的设计写的是 round >= 3 → publish，但这里有个矛盾：审核说“不行”，系统却强行输出。"
    "这是你要的设计吗？想想 workflow.py 是怎么处理的（它也有这个问题）。",
    "③ round 是在哪个节点 +1 的？translate 里，还是 review 里？"
    "这决定了 router 看到的数字是几。填错这里，整个循环次数就会差一次。",
]

FOOTER = "填完发给我。之后照着写代码，基本不会返工。"


# --------------------------------------------------------------------------
# docx 构造
# --------------------------------------------------------------------------
def esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def para(text: str, *, bold=False, size=22, style=None, spacing_after=120) -> str:
    """一个段落。size 单位是半磅：22 = 11pt。"""
    ppr = f'<w:spacing w:after="{spacing_after}"/>'
    if style:
        ppr += f'<w:pStyle w:val="{style}"/>'
    rpr = f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
    if bold:
        rpr += "<w:b/>"
    run = f'<w:r><w:rPr>{rpr}</w:rPr><w:t xml:space="preserve">{esc(text)}</w:t></w:r>'
    return f"<w:p><w:pPr>{ppr}</w:pPr>{run}</w:p>"


def cell(text: str, *, bold=False, width=1800, shade=None) -> str:
    rpr = '<w:sz w:val="18"/><w:szCs w:val="18"/>' + ("<w:b/>" if bold else "")
    shd = f'<w:shd w:val="clear" w:fill="{shade}"/>' if shade else ""
    p = (f'<w:p><w:pPr><w:spacing w:after="0"/></w:pPr>'
         f'<w:r><w:rPr>{rpr}</w:rPr><w:t xml:space="preserve">{esc(text)}</w:t></w:r></w:p>')
    return (f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{shd}'
            f'<w:vAlign w:val="center"/></w:tcPr>{p}</w:tc>')


def build_table() -> str:
    widths = [2600, 1500, 1500, 1100, 1000, 2000, 1800]
    # 表头
    hdr = "".join(cell(c, bold=True, width=w, shade="D9E2F3")
                  for c, w in zip(COLUMNS, widths))
    rows_xml = [f"<w:tr><w:trPr><w:tblHeader/></w:trPr>{hdr}</w:tr>"]
    # 空行留白多一点（填字用）
    for r in ROWS:
        cells = "".join(cell(v, width=w) for v, w in zip(r, widths))
        rows_xml.append(f"<w:tr><w:trPr><w:trHeight w:val=\"560\"/></w:trPr>{cells}</w:tr>")
    borders = (
        '<w:tblBorders>'
        '<w:top w:val="single" w:sz="6" w:color="999999"/>'
        '<w:left w:val="single" w:sz="6" w:color="999999"/>'
        '<w:bottom w:val="single" w:sz="6" w:color="999999"/>'
        '<w:right w:val="single" w:sz="6" w:color="999999"/>'
        '<w:insideH w:val="single" w:sz="4" w:color="CCCCCC"/>'
        '<w:insideV w:val="single" w:sz="4" w:color="CCCCCC"/>'
        '</w:tblBorders>')
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    return (f'<w:tbl><w:tblPr><w:tblW w:w="11500" w:type="dxa"/>{borders}</w:tblPr>'
            f"<w:tblGrid>{grid}</w:tblGrid>{''.join(rows_xml)}</w:tbl>")


def build_document() -> str:
    body = [para(TITLE, bold=True, size=32, spacing_after=200)]
    body.append(para("", size=12, spacing_after=60))
    for line in INTRO:
        body.append(para(line, size=20))
    body.append(para("", size=12, spacing_after=120))
    body.append(build_table())
    body.append(para("", size=12, spacing_after=200))
    body.append(para(NOTES_TITLE, bold=True, size=24, spacing_after=140))
    for line in NOTES:
        body.append(para(line, size=20))
    body.append(para("", size=12, spacing_after=120))
    body.append(para(FOOTER, bold=True, size=20))
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body>{"".join(body)}'
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/></w:sectPr>'
        "</w:body></w:document>"
    )


CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if OUT.exists():
        print(f"[覆盖] {OUT.name}")
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", build_document())
    size = OUT.stat().st_size
    print(f"[完成] {OUT}")
    print(f"       {size} 字节 · {len(ROWS)} 行待填 · {len(COLUMNS)} 列")
    print(f"       打开: notepad 不行，用 Word/WPS 打开")
    return 0


if __name__ == "__main__":
    sys.exit(main())
