from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools" / "clsplats"


def _text(name):
    return (TOOLS / name).read_text(encoding="utf-8")


def test_dockerfile_pins_versions():
    text = _text("Dockerfile")
    assert "nvidia/cuda:12.8.1-devel-ubuntu24.04" in text
    assert "587fffc207f9c7cbb348f35e6d1d223d007eab69" in text
    assert "torch==2.7.1" in text
    assert "torchvision==0.22.1" in text
    assert "cu128" in text
    assert "TORCH_CUDA_ARCH_LIST=12.0" in text
    assert "WANDB_MODE=disabled" in text


def test_run_script_uses_gpus_all():
    assert "--gpus all" in _text("run.sh")


def test_build_script_builds_local_image():
    assert "clsplats:local" in _text("build.sh")


def test_download_script_targets_level1_only():
    text = _text("download_v0.sh")
    assert "ackermannj/cl-splats-dataset" in text
    assert "Blender-Levels/Level-1/move/*" in text
