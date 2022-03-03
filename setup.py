import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

with open("requirements.txt", "r") as fh:
    requirements = fh.readlines()

setuptools.setup(
    name='PcBot',
    version=0.5,
    description='PcBot',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='',
    packages=setuptools.find_packages(),
    install_requires=requirements,

    entry_points={'console_scripts': [
        'pcbot = pcbot.PcBot:main'
    ]},
)
