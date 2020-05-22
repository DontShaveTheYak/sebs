import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="sebs",
    version="0.0.1",
    author="Levi Blaney",
    author_email="shadycuz",
    description="Create Stateful Elastic Block Storage on AWS.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/DontShaveTheYak/sebs",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GPLv3",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        'boto3',
        'ec2-metadata'
    ],
    scripts=['bin/sebs'],
    python_requires='>=3.6',
)
