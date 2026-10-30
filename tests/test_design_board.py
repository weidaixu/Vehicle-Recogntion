from pathlib import Path
from PIL import Image
from backend.board_renderer import render_board
def test_board_renderer_creates_image_and_manifest():
    paths=[next(Path("val/0000").glob("*.jpg"))]
    views=[{"url":f"/api/local-image/val/0000/{paths[0].name}","view_hint":"未标注视角"}]*3
    bid,img=render_board("0000","江铃_凯运",{"summary":"用于验证的设计语言摘要"},views,"tmp/boards_test")
    assert Image.open(img).size==(1800,1200)
    assert Path(f"tmp/boards_test/{bid}.json").exists()
