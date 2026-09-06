"""M2 任务 4.3：识别结果转储录制——真实框架识别产出解析核心的输入夹具。

对 test/fixtures/screenshots/ 的 27 张夹具逐节点 post_recognition（OCR 与
TemplateMatch 参数取 assets/resource/pipeline/genshin/observation.json），
节点名映射区域键后写 test/fixtures/ocr_dumps/<夹具主干>.json，形状为
{"区域键": [{"box": [x, y, w, h], "text": str, "score": float}, ...]}。
转储取识别详情的 filtered_results——流水线 replace 纠错只作用于该结果集
（all 为原始识别，2026-08-29 对 MaaFw 5.12.3 实测），与运行时消费一致。
2026-08-29 补强：带圈数字（强化次数标记）不再在识别层删除，保留进转储
（解析核心剥离层不动，M2.5 的强化次数读取以此为输入）。

绑定说明：maa 开发依赖的 wheel 未附带调试控制器库（MaaDbgControlUnit 缺失），
离线识别只需要资源，直接以 MaaTaskerBindResource 绑定 Resource，不绑控制器。

读取器归属（按界面）：fig1/fig3/fig6/fig7 与 L1…L13 为列表页；fig2/fig4/fig5
与 E1…E7 为强化页。fig6/fig7 为排序设置截图，同样跑列表页节点、如实记录。
"""

from __future__ import annotations

import json
from importlib.metadata import version
from pathlib import Path

import numpy as np
from PIL import Image
from maa.library import Library
from maa.pipeline import JOCR, JTemplateMatch
from maa.resource import Resource
from maa.tasker import Tasker

REPO_ROOT = Path(__file__).resolve().parents[1]
RESOURCE_DIR = REPO_ROOT / "assets/resource"
PIPELINE_JSON = RESOURCE_DIR / "pipeline/genshin/observation.json"
SCREENSHOT_DIR = REPO_ROOT / "test/fixtures/screenshots"
OUT_DIR = REPO_ROOT / "test/fixtures/ocr_dumps"

LIST_REGIONS = ("name", "slot", "main", "level", "substats", "set", "stars", "lock")
ENHANCE_REGIONS = ("breadcrumb", "main", "level", "exp", "substats", "mora", "fodder_tier")
LIST_FIXTURES = {"fig1", "fig3", "fig6", "fig7"}
ENHANCE_FIXTURES = {"fig2", "fig4", "fig5"}

# 识别质量复查线：区域最高分低于该值记为低分异常
LOW_SCORE = 0.6


def reader_of(stem: str) -> str:
    if stem in LIST_FIXTURES or stem.startswith("L"):
        return "list"
    if stem in ENHANCE_FIXTURES or stem.startswith("E"):
        return "enhance"
    raise ValueError(f"未知夹具主干：{stem}")


def build_param(node: dict):
    if node["recognition"] == "OCR":
        return JOCR(
            roi=tuple(node["roi"]),
            expected=node.get("expected", []),
            threshold=node["threshold"],
            only_rec=node.get("only_rec", False),
            replace=[tuple(pair) for pair in node.get("replace", [])],
        )
    return JTemplateMatch(
        template=node["template"],
        roi=tuple(node["roi"]),
        threshold=[node["threshold"]],
    )


def to_boxes(results) -> list[dict]:
    return [
        {
            "box": [int(v) for v in result.box],
            "text": getattr(result, "text", ""),
            "score": float(result.score),
        }
        for result in results
    ]


def check_shape(dump: dict, regions) -> None:
    """转储形状断言：区域键集合与文字框三键（box/text/score）。"""
    assert set(dump) == set(regions), (sorted(dump), sorted(regions))
    for boxes in dump.values():
        for frame in boxes:
            assert set(frame) == {"box", "text", "score"}, frame
            assert isinstance(frame["box"], list) and len(frame["box"]) == 4, frame
            assert all(isinstance(v, int) for v in frame["box"]), frame
            assert isinstance(frame["text"], str), frame
            assert isinstance(frame["score"], float), frame


def main() -> None:
    print("maa 版本：", version("MaaFw"))
    nodes = json.loads(PIPELINE_JSON.read_text(encoding="utf-8"))
    assert len(nodes) == 15, f"预期 15 个识别节点，实际 {len(nodes)}"

    resource = Resource()
    load = resource.post_bundle(RESOURCE_DIR)
    load.wait()
    assert load.succeeded, "资源加载失败"
    tasker = Tasker()
    assert Library.framework().MaaTaskerBindResource(tasker._handle, resource._handle), "Resource 绑定失败"

    stems = sorted(path.stem for path in SCREENSHOT_DIR.glob("*.png"))
    assert len(stems) == 27, f"预期 27 张夹具，实际 {len(stems)}"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    anomalies: list[str] = []
    for stem in stems:
        reader = reader_of(stem)
        regions = LIST_REGIONS if reader == "list" else ENHANCE_REGIONS
        with Image.open(SCREENSHOT_DIR / f"{stem}.png") as im:
            image = np.ascontiguousarray(np.array(im.convert("RGB"))[:, :, ::-1])

        dump: dict[str, list[dict]] = {}
        for region in regions:
            node = nodes[f"obs_{reader}_{region}"]
            job = tasker.post_recognition(node["recognition"], build_param(node), image)
            job.wait()
            assert job.succeeded, f"{stem}/{region} 识别任务执行失败"
            recognition = tasker.get_node_detail(job.get().node_id_list[0]).recognition
            dump[region] = to_boxes(recognition.filtered_results)
            if not dump[region] and region != "lock":
                # lock 空命中是正常语义（未锁定即无橙色挂锁），不算异常
                anomalies.append(f"{stem}: 区域 {region} 无识别结果")
            elif dump[region] and max(frame["score"] for frame in dump[region]) < LOW_SCORE:
                worst = min(dump[region], key=lambda frame: frame["score"])
                anomalies.append(
                    f"{stem}: 区域 {region} 低分（最高 {max(f['score'] for f in dump[region]):.2f}，"
                    f"最低框 {worst['text']!r} {worst['score']:.2f}）"
                )

        check_shape(dump, regions)
        (OUT_DIR / f"{stem}.json").write_text(
            json.dumps(dump, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        summary = " ".join(f"{key}={len(boxes)}" for key, boxes in dump.items())
        print(f"{stem}.json（{reader}页） {summary}")

    print(f"已生成 {len(stems)} 份转储 → {OUT_DIR.relative_to(REPO_ROOT)}")
    if anomalies:
        print(f"识别质量异常（{len(anomalies)} 条，如实记录）：")
        for line in anomalies:
            print("  -", line)
    else:
        print("识别质量复查未发现空区域或低分异常")


if __name__ == "__main__":
    main()
