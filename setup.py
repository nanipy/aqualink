import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()


requirements = []
with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setuptools.setup(
    name="aqualink",
    version="1.0.0",
    author="Gelbpunkt & F4stZ4p",
    author_email="aqualink@is-the.best",
    description="A better Python lavalink client",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/nanipy/aqualink",
    packages=setuptools.find_packages(),
    license="MIT",
    install_requires=requirements,
    classifiers=(
        "Programming Language :: Python :: 3.6",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ),
)
