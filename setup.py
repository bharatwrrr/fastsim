"""PyPI setup script.  To use it, run `python setup.py sdist bdist_wheel` from this directory."""

import setuptools
from setuptools_rust import RustExtension, Binding

import os
import sys
develop_mode = os.environ.get("DEVELOP_MODE", False)
if develop_mode:
    rust_extensions = []
    print("make sure to install the rust extensions manually\n cd rust; maturin develop;")
else:
    rust_extensions = [
        RustExtension(
            "fastsimrust",
            "rust/fastsim-py/Cargo.toml",
            binding=Binding.PyO3,
            py_limited_api=True,
        ),
    ]


with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    # rust extension
    rust_extensions=rust_extensions,
)