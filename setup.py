"""Bladerunner's (very simple) setup.py.

Installation instructions:

    $ python setup.py build
    $ sudo python setup.py install
"""


from distutils.core import setup


setup(
    name='Bladerunner',
    version='2.6',
    author='Adam Talsma',
    author_email='adam@demonware.net',
    package_dir={'bladerunner': 'src'},
    packages=['bladerunner'],
    scripts=['bin/bladerunner'],
    url='https://github.com/a-tal/bladerunner',
    description='serial execution of commands on hosts',
    long_description=(
        "Bladerunner provides an easy to use interface to quickly audit or push"
        " changes to a multitude of hosts. It uses pexpect, so pattern matching"
        " is at its heart (for better and for worse). Be aware of returning to "
        "a shell prompt after every command executed. Several options are "
        "available for custom networking and host setups."
        ),
    download_url='https://github.com/a-tal/bladerunner/downloads',
    license="BSD",
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: BSD License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Topic :: System :: Clustering',
        'Topic :: System :: Systems Administration',
        ],
    )
