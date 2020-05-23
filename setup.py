import os
import datetime
import subprocess
import setuptools


release_version = os.getenv('RELEASE_VERSION')

if not release_version:
    tag = subprocess.check_output(
        ["git", "describe", "--abbrev=0"]
    ).strip().decode('ASCII')

    now = datetime.datetime.now()

    release_version = f'{tag}.dev{now.hour}{now.minute}'


with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="sebs",
    version=release_version,
    author="Levi Blaney",
    author_email="shadycuz@gmail.com",
    description="Create Stateful Elastic Block Storage on AWS.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/DontShaveTheYak/sebs",
    packages=setuptools.find_packages(),
    classifiers=[
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: POSIX :: Linux",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    install_requires=[
        'boto3',
        'ec2-metadata',
        'importlib-metadata ~= 1.0 ; python_version < "3.8"'
    ],
    scripts=['bin/sebs'],
    python_requires='>=3.6',
)
