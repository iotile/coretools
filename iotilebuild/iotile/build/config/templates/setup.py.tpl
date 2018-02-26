from setuptools import setup, find_packages

setup(
    name="{{ name }}",
    packages=find_packages(include=["{{ package }}.*", "{{ package }}"]),
    version="{{ version }}",
    install_requires={{ deps }},
    entry_points={{ entry_points }},
    author="Arch",
    author_email="info@arch-iot.com"
)
