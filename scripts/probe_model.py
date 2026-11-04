"""Record task-independent text and image requests after deployment."""
import base64
import io
import json
from pathlib import Path
import time
import urllib.request

from PIL import Image, ImageDraw

project = Path(__file__).resolve().parents[1]
config = json.loads((project / "configs/model/qwen35b.json").read_text())
runtime = (project / Path(config["runtime_root"]).expanduser()).resolve()
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def picture(shape):
    image = Image.new("RGB", (448, 448), "white")
    draw = ImageDraw.Draw(image)
    if shape == "square":
        draw.rectangle((110, 110, 338, 338), fill="red")
    else:
        draw.ellipse((110, 110, 338, 338), fill="blue")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return {"type": "image_url", "image_url": {
        "url": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
    }}


cases = [
    ("text", [{"type": "text", "text": "Reply with exactly: READY"}]),
    ("single_image", [picture("square"), {"type": "text", "text": "Name the shape and its color. One short sentence."}]),
    ("two_images", [picture("square"), picture("circle"), {"type": "text", "text": "Name the shape and color in each image, in order. Two short sentences."}]),
]
results = []
for name, content in cases:
    payload = {"model": config["served_model_name"], "messages": [{"role": "user", "content": content}],
               "temperature": 0, "max_tokens": 128, "chat_template_kwargs": {"enable_thinking": False}}
    request = urllib.request.Request(
        f'http://127.0.0.1:{config["port"]}/v1/chat/completions',
        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"},
    )
    start = time.perf_counter()
    with opener.open(request, timeout=300) as response:
        data = json.load(response)
    item = {"case": name, "wall_seconds": time.perf_counter() - start,
            "response": data["choices"][0]["message"], "usage": data.get("usage"),
            "finish_reason": data["choices"][0].get("finish_reason")}
    results.append(item)
    print(json.dumps(item, ensure_ascii=False), flush=True)
(runtime / "manifests/service_probe.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
