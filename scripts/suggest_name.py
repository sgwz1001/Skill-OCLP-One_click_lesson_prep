#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
suggest_name.py — 依据「文件名-文件类型-时间-v版本号&备注」规范，
扫描目标目录中同主题文件，按版本递增规则计算下一个建议文件名。

版本递增规则（核心）：
  - 跨天（哪怕只改一点点）：主版本 +1，日期更新为当天  例 v1 -> v2
  - 大篇幅重构 / 大改     ：主版本 +1                   例 v2 -> v3
  - 同一天多次小幅修改   ：次版本 +0.1，日期不变        例 v1 -> v1.1 -> v1.2

用法：
  python suggest_name.py --theme "平台首页效果预览" --type "效果预览网页" \
      --ext html --note "微调了UI布局" --dir "./output" [--major] [--date 20260801]

参数说明：
  --theme   文件名主体（必填），如 "三方共同运营合同"
  --type    文件类型描述（必填），如 "合同" / "数据表格" / "效果预览网页"
  --ext     扩展名（不含点），如 docx / xlsx / html；留空表示无扩展名
  --note    备注（可选），如 "按照企业规范与老国标版本"
  --dir     扫描目录（默认当前目录）
  --date    指定日期 YYYYMMDD（默认今天）
  --major   强制主版本 +1（用于大篇幅重构 / 大改场景）
  --json    以 JSON 输出完整拆解（默认仅输出文件名）

输出：标准文件名，例如
  平台首页效果预览-效果预览网页-20260801-v1.3&微调了UI布局.html
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime


# Windows / 各平台文件名非法字符
_ILLEGAL = re.compile(r'[\\/:*?"<>|]')


def _sanitize(text: str) -> str:
    """清洗会破坏文件名的字符，并把连续空白压缩为单个空格。"""
    if not text:
        return ""
    text = _ILLEGAL.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_version(ver: str):
    """将 '1' -> (1, 0)，'1.3' -> (1, 3)。返回 (major, minor) 元组。"""
    parts = ver.split(".")
    try:
        major = int(parts[0])
    except ValueError:
        major = 1
    minor = 0
    if len(parts) > 1:
        try:
            minor = int(parts[1])
        except ValueError:
            minor = 0
    return (major, minor)


def _next_version(latest, today_date: str, major_change: bool):
    """
    根据规则与已存在的最新版本，返回 (version_str, date_to_use)。

    latest: (date_str, (major, minor)) 或 None
    """
    if latest is None:
        return ("1", today_date)

    latest_date, (mj, mn) = latest

    if today_date > latest_date:
        # 跨天：主版本 +1，日期更新为当天
        return (str(mj + 1), today_date)
    if today_date < latest_date:
        # 指定日期早于已有最新版本（异常情况）：仍主版本 +1 以免覆盖
        return (str(mj + 1), today_date)
    # 同一天
    if major_change:
        return (str(mj + 1), today_date)
    # 同日小幅：次版本 +0.1
    if mn == 0:
        return (f"{mj}.1", today_date)
    return (f"{mj}.{mn + 1}", today_date)


def suggest(theme, ftype, ext, note, directory, date_str, major_change):
    theme = _sanitize(theme)
    ftype = _sanitize(ftype)
    note = _sanitize(note)
    if not ext:
        ext = ""
    else:
        ext = ext.lstrip(".")

    # 匹配：<theme>-<type>-<YYYYMMDD>-v<ver>[&<note>].<ext>
    escaped_theme = re.escape(theme)
    escaped_type = re.escape(ftype)
    if ext:
        pattern = re.compile(
            rf"^{escaped_theme}-{escaped_type}-(\d{{8}})-v([\d.]+)(?:&(.*?))?\.{re.escape(ext)}$"
        )
    else:
        pattern = re.compile(
            rf"^{escaped_theme}-{escaped_type}-(\d{{8}})-v([\d.]+)(?:&(.*?))?$"
        )

    best = None  # (date_str, (major, minor))
    found = []
    try:
        entries = os.listdir(directory)
    except FileNotFoundError:
        entries = []

    for name in entries:
        m = pattern.match(name)
        if not m:
            continue
        d = m.group(1)
        ver = _parse_version(m.group(2))
        found.append((d, ver, name))
        key = (d, ver)
        if best is None or key > best:
            best = key

    version, date_used = _next_version(best, date_str, major_change)

    core = f"{theme}-{ftype}-{date_used}-v{version}"
    if note:
        core += f"&{note}"
    filename = core + (f".{ext}" if ext else "")

    return {
        "filename": filename,
        "theme": theme,
        "type": ftype,
        "date": date_used,
        "version": version,
        "note": note,
        "ext": ext,
        "existing_count": len(found),
        "latest_existing": found[-1][2] if found else None,
    }


def main():
    ap = argparse.ArgumentParser(description="按命名规范建议新文件名")
    ap.add_argument("--theme", required=True, help="文件名主体")
    ap.add_argument("--type", required=True, help="文件类型描述")
    ap.add_argument("--ext", default="", help="扩展名（不含点）")
    ap.add_argument("--note", default="", help="备注")
    ap.add_argument("--dir", default=".", help="扫描目录，默认当前目录")
    ap.add_argument("--date", default=None, help="指定日期 YYYYMMDD，默认今天")
    ap.add_argument("--major", action="store_true", help="强制主版本 +1")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出完整拆解")
    args = ap.parse_args()

    if args.date:
        date_str = args.date
    else:
        date_str = datetime.now().strftime("%Y%m%d")

    # 校验日期格式
    if not re.fullmatch(r"\d{8}", date_str):
        print("错误：--date 必须为 YYYYMMDD 格式，例如 20260801", file=sys.stderr)
        sys.exit(2)

    result = suggest(
        theme=args.theme,
        ftype=args.type,
        ext=args.ext,
        note=args.note,
        directory=args.dir,
        date_str=date_str,
        major_change=args.major,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["filename"])


if __name__ == "__main__":
    main()
