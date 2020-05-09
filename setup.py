import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="sebs-test",
    version="0.0.1",
    author="Levi Blaney",
    author_email="shadycuz",
    description="Create Stateful Elastic Block Device",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/DontShaveTheYak/sebs",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        'boto3',
        'ec2-metadata'
    ],
    python_requires='>=3.6',
)
