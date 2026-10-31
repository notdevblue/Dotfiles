#!/usr/bin/env python3
"""Rebuild source-aligned character alpha; never synthesize or change source RGB.

Run with Python containing numpy, OpenCV and Pillow, e.g. the local Forge venv.
The outlines use the original retouched image coordinates (half SwinIR size).
Only a narrow boundary band is classified by GrabCut; all scenery outside it
is hard background, and the character interior is hard foreground.
"""
from pathlib import Path
import hashlib
import argparse
import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
SPECS = {
    "landscape": {
        "source": "wallpaper-landscape-swinir.png",
        "sha256": "aa7cb939dfba132e547dd9405fca801c14e45d8f4299c85a435b7bfd4176c5ef",
        "size": (3876, 1624),
        "outline": [
            (1351,812),(1357,794),(1366,771),(1374,750),(1384,724),
            (1378,725),(1370,727),(1368,724),(1375,704),(1366,719),
            (1360,726),(1356,725),(1360,715),(1368,694),(1376,672),
            (1379,658),(1385,637),(1390,619),(1398,599),(1405,579),
            (1411,559),(1419,537),(1414,524),(1414,516),(1408,502),
            (1407,490),(1414,478),(1420,467),(1420,458),(1417,448),
            (1419,438),(1425,426),(1434,418),(1434,412),(1431,410),
            (1430,402),(1442,393),(1456,384),(1474,376),(1493,368),
            (1498,365),(1495,359),(1486,355),(1473,352),(1452,351),
            (1432,349),(1424,345),(1422,338),(1421,322),(1417,311),
            (1417,302),(1414,295),(1415,287),(1417,279),(1415,267),
            (1415,262),(1427,261),(1438,258),(1446,254),(1454,247),
            (1455,239),(1448,242),(1443,240),(1438,234),(1434,232),
            (1428,232),(1424,224),(1422,211),(1420,204),(1418,213),
            (1418,224),(1415,223),(1411,219),(1411,208),(1415,191),
            (1423,176),(1431,163),(1440,150),(1450,137),(1461,126),
            (1475,116),(1490,108),(1509,101),(1524,98),(1539,99),
            (1554,100),(1570,94),(1582,94),(1594,97),(1602,98),
            (1597,92),(1594,87),(1594,79),(1598,70),(1605,61),
            (1616,50),(1632,40),(1649,32),(1665,29),(1682,29),
            (1698,32),(1713,36),(1728,42),(1740,48),(1747,60),
            (1753,72),(1759,84),(1763,98),(1766,113),(1764,127),
            (1757,140),(1749,149),(1733,158),(1721,161),
            (1728,175),(1736,190),(1744,214),(1750,235),(1754,253),
            (1757,272),(1756,289),(1751,307),(1744,320),(1733,331),
            (1725,335),(1727,340),(1733,346),(1735,358),(1741,367),
            (1752,371),(1763,379),(1765,392),(1763,405),(1764,414),
            (1775,419),(1791,426),(1805,435),(1815,445),(1819,454),
            (1815,460),(1812,470),(1814,480),(1817,491),(1816,502),
            (1813,513),(1813,520),(1818,532),(1815,542),(1811,552),
            (1810,561),(1819,577),(1831,601),(1840,626),(1847,650),
            (1851,660),(1854,670),(1857,680),(1860,690),(1864,700),
            (1867,710),(1870,720),(1873,730),(1875,740),(1878,750),
            (1880,760),(1883,770),(1885,780),(1888,790),(1891,800),
            (1895,812),
        ],
    },
    "portrait": {
        "source": "wallpaper-portrait-swinir.png",
        "sha256": "25a0b41803883c1d5f395fa7fd151e066568cad3cc45030c2af3079d0400449f",
        "size": (1624, 3870),
        "outline": [
            (371,1935),(367,1930),(364,1925),(361,1920),(358,1915),
            (356.5,1910),(357,1900),(358.5,1890),(362,1880),(366,1868),
            (370,1856),(368,1845),(366,1829),(366,1809),(369,1787),
            (376,1763),(386,1735),(400,1705),(410,1673),(419,1642),
            (427,1611),(439,1581),(446,1563),
            (442,1564),(436,1566),(432,1564),(434,1555),(441,1536),
            (430,1557),(425,1564),(421,1564),(424,1555),(434,1527),
            (437,1514),(441,1502),(443,1489),(449,1470),(456,1450),
            (463,1427),(472,1404),(476,1396),(474,1385),(473,1374),
            (469,1366),(468,1354),(471,1342),(479,1330),(478,1322),
            (478,1315),(480,1308),(487,1299),(493,1293),(494,1288),
            (491,1285),(491,1278),(503,1269),(521,1260),(540,1252),
            (552,1246),(550,1240),(542,1235),(525,1232),(508,1230),
            (496,1227),(490,1222),(488,1210),(488,1199),(485,1191),
            (483,1185),(485,1176),(483,1167),(482,1155),(483,1152),
            (498,1151),(508,1148),(516,1143),(521,1137),(522,1130),
            (514,1136),(509,1135),(503,1130),(497,1128),(493,1123),
            (489,1116),(488,1108),(486,1117),(486,1125),(481,1122),
            (480,1114),(481,1102),(486,1088),(494,1074),(503,1060),
            (514,1047),(527,1036),(541,1027),(557,1019),(571,1016),
            (585,1014),(597,1015),(607,1015),(617,1011),(629,1011),
            (638,1013),(635,1008),(632,1003),(632,995),(636,984),
            (645,974),(656,965),(670,958),(686,954),(702,952),
            (718,955),(734,960),(749,966),(759,975),(766,988),
            (772,1004),(775,1020),(774,1034),(769,1047),(760,1056),
            (747,1064),(739,1066),(744,1078),(751,1094),(756,1112),
            (761,1135),(765,1158),(766,1175),(763,1191),(757,1206),
            (749,1215),(748,1220),(754,1227),(757,1238),(762,1246),
            (775,1250),(780,1258),(780,1270),(777,1283),(782,1290),
            (798,1297),(812,1304),(812,1935),
        ],
    },
}


def build(name, spec):
    path = ROOT / "assets" / spec["source"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == spec["sha256"], path
    source = np.asarray(Image.open(path).convert("RGB"))
    height, width = source.shape[:2]
    assert (width, height) == spec["size"]
    points = np.rint(np.array(spec["outline"], dtype=np.float32) * 2).astype(np.int32)
    # A small ROI keeps the large portrait sky out of the classifier entirely.
    x0 = max(0, int(points[:, 0].min()) - 16)
    y0 = max(0, int(points[:, 1].min()) - 16)
    image = np.ascontiguousarray(source[y0:, x0:, ::-1])
    shape = image.shape[:2]
    polygon = np.zeros(shape, np.uint8)
    cv2.fillPoly(polygon, [points - (x0, y0)], 255)
    radius = 7  # 3.5 original pixels; cannot swallow nearby scenery.
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius * 2 + 1,) * 2)
    inside = cv2.erode(polygon, kernel)
    outside = cv2.dilate(polygon, kernel)
    trimap = np.full(shape, cv2.GC_BGD, np.uint8)
    trimap[outside > 0] = cv2.GC_PR_BGD
    trimap[polygon > 0] = cv2.GC_PR_FGD
    trimap[inside > 0] = cv2.GC_FGD
    # The character continues through the source frame; never erode that edge.
    trimap[-radius:, polygon[-1] > 0] = cv2.GC_FGD
    if name == "portrait":
        trimap[polygon[:, -1] > 0, -radius:] = cv2.GC_FGD
    cv2.setRNGSeed(0)
    cv2.grabCut(image, trimap, None, np.zeros((1, 65)), np.zeros((1, 65)),
                5, cv2.GC_INIT_WITH_MASK)
    selected = np.isin(trimap, (cv2.GC_FGD, cv2.GC_PR_FGD)).astype(np.uint8)
    # Retain the contiguous character, dropping detached classified sky flecks.
    count, labels, stats, _ = cv2.connectedComponentsWithStats(selected, 8)
    largest = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    selected = (labels == largest).astype(np.uint8) * 255
    # Branches and railing can share coat colors. Constrain those boundaries
    # to the traced silhouette with only one original pixel of tolerance.
    near = cv2.dilate(polygon, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    yy, xx = np.indices(shape)
    if name == "landscape":
        constrained = ((xx + x0 > 1760*2) & (yy + y0 > 380*2))
    else:
        constrained = ((xx + x0 < 450*2) & (yy + y0 > 1580*2))
    selected[constrained & (near == 0)] = 0
    if name == "landscape":
        # At the dark coat, the railing behind has almost the same palette.
        # The hand-traced outside edge is the reliable boundary there.
        selected[(yy+y0 > 630*2) & (polygon == 0)] = 0
    else:
        # The pale coat's warm/blue transition separates its silhouette from
        # even the snow-covered railing. Refine only this long plain edge.
        chroma = image[:, :, 2].astype(np.float32) - image[:, :, 0]
        chroma = cv2.GaussianBlur(chroma, (3,3), 0.6)
        rows = np.arange(max(0,1580*2-y0),shape[0])
        edges = []
        for row in rows:
            boundary = np.flatnonzero(polygon[row])[0]
            candidates = np.arange(max(0,boundary-10), min(shape[1],boundary+11))
            # Require sustained warm coat color rather than a single branch
            # gradient. Original antialiased scenery at the boundary is omitted.
            warm = [x for x in candidates if np.min(chroma[row,x:x+4]) >= 12]
            edges.append(float(warm[0] if warm else boundary))
        # Median smoothing rejects individual crossing branches; the Gaussian
        # then follows the coat's gradual curve rather than staircase artifacts.
        edge_array = np.array(edges, np.float32)
        padded = np.pad(edge_array, 15, mode="edge")
        edges = np.array([np.median(padded[n:n+31]) for n in range(len(edges))])
        edges = cv2.GaussianBlur(edges.reshape(-1,1), (1,31), 5).ravel()
        for row, edge_x in zip(rows,edges):
            selected[row,:int(np.ceil(edge_x))] = 0
            selected[row,int(np.ceil(edge_x)):min(shape[1],int(edge_x)+20)] = 255
    # Less than one source pixel of antialiasing; no wide matte feather/halo.
    edge = cv2.GaussianBlur(selected, (3, 3), 0.45)
    alpha = np.zeros((height, width), np.uint8)
    alpha[y0:, x0:] = edge
    rgba = np.full((height, width, 4), 255, np.uint8)
    rgba[:, :, 3] = alpha
    output = ROOT / "assets" / f"character-{name}-matte.png"
    Image.fromarray(rgba).save(output, optimize=True)
    # Validate required mask contract independently of its file representation.
    written = np.asarray(Image.open(output))
    assert written.shape == (height, width, 4)
    assert np.all(written[:, :, :3] == 255)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == spec["sha256"]
    print(f"{output.relative_to(ROOT)}: {width}x{height}; "
          f"opaque={np.count_nonzero(alpha == 255)}; partial={np.count_nonzero((alpha > 0) & (alpha < 255))}")
    return source, alpha


def comparison(items):
    panels = []
    for name, (rgb, alpha) in items.items():
        ys, xs = np.nonzero(alpha)
        box = (max(0, xs.min()-24), max(0, ys.min()-24), rgb.shape[1], rgb.shape[0])
        source = Image.fromarray(rgb).crop(box)
        a = Image.fromarray(alpha).crop(box)
        thumbs = [source]
        for color in ("#1e191f", "#eee8dd"):
            panel = Image.new("RGB", source.size, color)
            panel.paste(source, mask=a)
            thumbs.append(panel)
        scale = min(1, 900 / source.height, 500 / source.width)
        size = (round(source.width*scale), round(source.height*scale))
        row = Image.new("RGB", (size[0]*3, size[1]+24), "#222222")
        draw = ImageDraw.Draw(row)
        for index, (thumb, label) in enumerate(zip(thumbs, ("Original", "Alpha on #1E191F", "Alpha on light"))):
            row.paste(thumb.resize(size, Image.Resampling.LANCZOS), (size[0]*index, 24))
            draw.text((size[0]*index+5, 5), f"{name}: {label}", fill="white")
        panels.append(row)
    canvas = Image.new("RGB", (max(p.width for p in panels), sum(p.height for p in panels)), "#222222")
    y = 0
    for panel in panels:
        canvas.paste(panel, (0,y)); y += panel.height
    destination = ROOT / "verification" / "character-mattes.png"
    destination.parent.mkdir(exist_ok=True)
    canvas.save(destination)
    print(destination.relative_to(ROOT))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    results = {name: build(name, spec) for name, spec in SPECS.items()}
    if args.preview:
        comparison(results)
