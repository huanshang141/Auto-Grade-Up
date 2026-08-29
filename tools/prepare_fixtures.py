"""M2 任务 4.1：截图夹具处理——统一缩放到 1280×720、涂黑右下角 UID 后入库。

读 reference/pic/（图1…图7，主干映射为 fig1…fig7）与 reference/pic2/（补拍
11 张，沿用来源文件名主干 L1…L8、E1…E3）→ 缩放到 1280×720 → 涂黑 UID 区域
→ 写 test/fixtures/screenshots/。不改动 reference/；处理可重复执行（幂等）。
隐私口径（2026-08-29 定案）：仅遮挡 UID，游戏角色名视为公共内容不遮挡。
"""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[1]
PIC_DIR = REPO_ROOT / "reference/pic"
PIC2_DIR = REPO_ROOT / "reference/pic2"
OUT_DIR = REPO_ROOT / "test/fixtures/screenshots"

TARGET_SIZE = (1280, 720)
# UID 显示于右下角（1080p 原图约 x1697-1860、y1055-1074，两界面位置一致）；
# 遮挡矩形按 720 坐标取值并留裕量，上方避开「强化」按钮
UID_MASK_RECT_720 = (1107, 695, 1275, 720)


def fixture_stem(path: Path) -> str:
    """来源文件名主干：pic/ 的「图N-*」映射为 figN，pic2/ 沿用原名主干。"""
    matched = re.match(r"图(\d+)", path.stem)
    if matched:
        return f"fig{matched.group(1)}"
    return path.stem


def prepare() -> list[Path]:
    sources = sorted(PIC_DIR.glob("*.png")) + sorted(PIC2_DIR.glob("*.png"))
    assert len(sources) == 18, f"预期 18 张来源截图，实际 {len(sources)}"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = []
    for source in sources:
        with Image.open(source) as im:
            canvas = im.convert("RGB").resize(TARGET_SIZE, Image.LANCZOS)
        ImageDraw.Draw(canvas).rectangle(UID_MASK_RECT_720, fill=(0, 0, 0))
        target = OUT_DIR / f"{fixture_stem(source)}.png"
        canvas.save(target, "PNG")
        outputs.append(target)
    return outputs


def self_check(outputs: list[Path]) -> None:
    """每张夹具复查：尺寸 1280×720、UID 遮挡区域全黑。"""
    for target in outputs:
        with Image.open(target) as check:
            assert check.size == TARGET_SIZE, f"尺寸不符：{target}"
            extrema = check.crop(UID_MASK_RECT_720).getextrema()
            assert extrema == ((0, 0), (0, 0), (0, 0)), f"UID 区域未涂黑：{target}"


def main() -> None:
    outputs = prepare()
    self_check(outputs)
    print(f"已生成并自检 {len(outputs)} 张夹具 → {OUT_DIR.relative_to(REPO_ROOT)}")
    for path in outputs:
        print(f"  {path.name}")


if __name__ == "__main__":
    main()
