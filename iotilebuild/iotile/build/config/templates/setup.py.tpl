from setuptools import setup, find_packages

setup(
    name="{{ name }}",
    packages=find_packages(include=["{{ package }}.*", "{{ package }}"]),
    version="{{ version }}",
    install_requires={{ deps }},
    entry_points={{ entry_points }},
    include_package_data={{ include_package_data }},
    author="Arch",
    author_email="info@arch-iot.com"
)
