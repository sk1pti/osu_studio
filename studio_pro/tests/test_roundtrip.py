# -*- coding: utf-8 -*-
from studio_pro.core.parser import parse_osu, serialize_obj

SAMPLE = '''osu file format v14

[General]
SliderMultiplier:1.4

[TimingPoints]
0,333.33,4,2,1,60,1,0

[HitObjects]
256,192,1000,1,0,0:0:0:0:
100,100,2000,2,0,L|200:200,1,140
300,300,3000,8,0,3500
'''

def test_roundtrip():
    i1 = parse_osu(SAMPLE)
    assert len(i1["objs"]) == 3
    head = SAMPLE.split("[HitObjects]")[0] + "[HitObjects]\n"
    tail = "\n".join(serialize_obj(o) for o in i1["objs"])
    i2 = parse_osu(head + tail)
    for a, b in zip(i1["objs"], i2["objs"]):
        assert a["kind"] == b["kind"]
        assert (a["x"], a["y"], a["t"], a["end"]) == (b["x"], b["y"], b["t"], b["end"])

def test_curve_type_kept():
    src = SAMPLE.replace("L|200:200", "P|200:200|250:150")
    s = [o for o in parse_osu(src)["objs"] if o["kind"] == "slider"][0]
    assert serialize_obj(s).split(",")[5].startswith("P")
