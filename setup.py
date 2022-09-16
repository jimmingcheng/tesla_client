from setuptools import setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='tesla_client',
    version='2.0.0',
    description='Tesla API Client',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='',
    author='Jimming Cheng',
    author_email='jimming@gmail.com',
    packages=['tesla_client'],
    install_requires=[
        'requests',
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
