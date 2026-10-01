from setuptools import find_packages, setup

with open("requirements.txt") as f:
    requirements = [
        line.strip() for line in f
        if line.strip() and not line.startswith("-e") and not line.startswith("#")
    ]

setup(
    name="hackdata",
    version="0.1.0",
    packages=find_packages(),
    install_requires=requirements,
)
