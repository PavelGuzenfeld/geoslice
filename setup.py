#!/usr/bin/env python
"""Setup script - use pip install . for normal install."""

import os
import sys
from pathlib import Path

# Always use setuptools for editable installs or when GEOSLICE_PYTHON_ONLY is set
PYTHON_ONLY = (
    os.environ.get("GEOSLICE_PYTHON_ONLY", "0") == "1" or 
    "--editable" in sys.argv or
    "-e" in sys.argv
)

from setuptools import setup, find_packages

setup(
    name="geoslice",
    version="0.0.1",
    description="Ultra-fast geospatial windowing with zero-copy memory mapping",
    long_description=Path("README.md").read_text() if Path("README.md").exists() else "",
    long_description_content_type="text/markdown",
    author="GeoSlice Authors",
    license="MIT",
    packages=find_packages(where="python"),
    package_dir={"": "python"},
    package_data={"geoslice": ["py.typed"]},
    install_requires=["numpy>=1.20"],
    extras_require={
        "convert": ["rasterio>=1.3"],
        "dev": ["pytest>=7.0", "pytest-benchmark>=4.0", "rasterio>=1.3"],
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: GIS",
    ],
)
