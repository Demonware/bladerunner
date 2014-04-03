"""Bladerunner's setup.py."""


from setuptools import setup


with open("bladerunner/__init__.py", "r") as openinit:
    for line in openinit.readlines():
        if line.startswith("__version__ ="):
            __version__ = line[14:].replace('"', "").replace('"', "").strip()
            break
    else:
        __version__ = "0.0-version-unknown"


setup(
    name="bladerunner",
    version=__version__,
    author="Adam Talsma",
    author_email="adam@demonware.net",
    packages=["bladerunner"],
    install_requires=["pexpect >= 3.0", "futures"],
    scripts=["bin/bladerunner"],
    url="https://github.com/Demonware/bladerunner",
    description="Execution of commands on hosts",
    long_description=(
        "Bladerunner provides an easy to use interface to quickly audit or "
        "push changes to a multitude of hosts. It uses pexpect, so pattern "
        "matching is at its heart. Be aware of returning to a shell prompt "
        "after every command executed. Several options are available for "
        "custom networking and host setups."
    ),
    download_url="https://github.com/Demonware/bladerunner",
    tests_require=["nose", "tornado"],
    test_suite="nose.collector",
    license="BSD",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: BSD License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Topic :: System :: Clustering",
        "Topic :: System :: Systems Administration",
    ],
)
