from setuptools import setup

setup(
    name="{{ name }}",
    packages=[{{ "\"%s\"" % package }}],
    version="{{ version }}",
    install_requires={{ deps }},
    entry_points={{ entry_points }},
    author="Arch",
    author_email="info@arch-iot.com"
)
