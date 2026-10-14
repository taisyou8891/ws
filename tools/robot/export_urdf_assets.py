#!/usr/bin/env python3
"""URDF が参照するメッシュをコピーし、コメントを除いた URDF を書き出す。

URDF 中の package://<パッケージ名>/<相対パス> のメッシュを
<out_dir>/<パッケージ名>/<相対パス> にコピーする。package:// の書き方は変えない。
参照先が 1 つでも見つからなければ、何も書かずに終了コード 1 で止まる。
"""

import argparse
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--urdf", required=True, help="xacro で作った URDF")
    p.add_argument("--package_name", required=True, help="パッケージ名")
    p.add_argument("--package_dir", required=True, help="パッケージのディレクトリ")
    p.add_argument("--out_dir", required=True, help="出力先")
    p.add_argument("--out_name", required=True, help="URDF のファイル名")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    prefix = "package://%s/" % args.package_name
    package_dir = Path(args.package_dir)
    out_dir = Path(args.out_dir)

    # ET.parse は既定でコメントを捨てる
    tree = ET.parse(args.urdf)
    root = tree.getroot()

    rels = []
    for elem in root.iter():
        filename = elem.get("filename")
        if filename and filename.startswith(prefix):
            rel = filename[len(prefix):]
            if rel not in rels:
                rels.append(rel)

    missing = [r for r in rels if not (package_dir / r).is_file()]
    if missing:
        for r in missing:
            print("メッシュが見つからない: %s" % r, file=sys.stderr)
        return 1

    for rel in rels:
        dst = out_dir / args.package_name / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(package_dir / rel, dst)

    out_dir.mkdir(parents=True, exist_ok=True)
    ET.indent(tree, space="  ")
    tree.write(out_dir / args.out_name, encoding="utf-8", xml_declaration=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
