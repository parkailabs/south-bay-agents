"""Setup file for South Bay Prospecting Assistant."""

from setuptools import setup, find_packages

setup(
    name="southbay",
    version="1.0.0",
    description="Title Rep Prospecting Assistant for South Bay LA",
    packages=find_packages(),
    install_requires=[
        "click>=8.1.0",
        "rich>=13.0.0",
        "python-dateutil>=2.8.0",
        "tabulate>=0.9.0",
    ],
    entry_points={
        "console_scripts": [
            "southbay=southbay.cli:main",
        ],
    },
    python_requires=">=3.8",
)
