import os
import sys
from setuptools import setup, find_packages
from pip.req import parse_requirements


def get_requirements():
    requirements = [
        str(ir.req) for ir in parse_requirements(
            os.path.join(os.path.abspath(os.path.dirname(__file__)), 'requirements.txt'),
            session=False
        )
    ]
    if sys.version_info.major == 2:
        requirements.append("mock")
    return requirements


def read_file(filename):
    """
    Read a file into a string
    """
    path = os.path.abspath(os.path.dirname(__file__))
    filepath = os.path.join(path, filename)
    try:
        return open(filepath).read()
    except IOError:
        return ''


def get_readme():
    """
    Return the README file contents. Supports text ,rst, and markdown
    """
    for name in ('README', 'README.rst', 'README.md'):
        if os.path.exists(name):
            return read_file(name)
    return ''

# Use the docstring of the __init__ file to be the description
__import__('feedmapper')
DESC = " ".join(sys.modules['feedmapper'].__doc__.splitlines()).strip()

setup(
    name="django-feedmapper",
    version=sys.modules['feedmapper'].get_version().replace(' ', '-'),
    url='https://github.com/natgeo/django-feedmapper',
    license='BSD',
    author='Alexey Prokoptsev',
    author_email='aprokoptsev@gmail.com',
    description=DESC,
    long_description=get_readme(),
    packages=find_packages(),
    namespace_packages=[],
    include_package_data=True,
    install_requires=get_requirements(),
    classifiers=[
        'Environment :: Web Environment',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.4",
        'Framework :: Django',
        'Framework :: Django :: 1.7',
        'Framework :: Django :: 1.8',
        'Framework :: Django :: 1.9',
    ],
    test_suite='runtests.runtests',
)
