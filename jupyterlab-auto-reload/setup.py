from pathlib import Path
from setuptools import setup

HERE = Path(__file__).parent
LABEXTENSION_DIR = "share/jupyter/labextensions/jupyterlab-auto-reload"

# 收集 labextension 目录下的所有文件
data_files = []
ext_dir = HERE / "jupyterlab_auto_reload" / "labextension"
for f in ext_dir.rglob("*"):
    if f.is_file():
        rel_path = str(f.relative_to(HERE.parent.parent))  # 从 sys.prefix 开始的相对路径
        # 实际上 data_files 是 (target_dir, [source_files])
        target = f"{LABEXTENSION_DIR}/{f.relative_to(ext_dir).parent}"
        if target.endswith("/."):
            target = target[:-2]
        data_files.append((target, [str(f)]))

setup(
    name="jupyterlab-auto-reload",
    version="0.1.0",
    description="Auto-reload JupyterLab Notebook when file changes on disk",
    packages=["jupyterlab_auto_reload"],
    package_data={"jupyterlab_auto_reload": ["labextension/**/*"]},
    include_package_data=True,
    install_requires=[],
    python_requires=">=3.10",
)
