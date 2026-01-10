from setuptools import setup, find_packages

setup(
    name='devws',
    version='0.2.0',
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'devws': ['unsafe-patterns.yaml', 'startup.sh', 'resources/*'],
    },
    install_requires=[
        'Click',
        'PyYAML',
        'rich',
        'google-cloud-secret-manager', # Runtime dependency for secrets commands
        'importlib-metadata; python_version < "3.10"',
    ],
    extras_require={
        'tests': [
            'pytest',
            'pytest-mock',
        ],
    },
    entry_points={
        'console_scripts': [
            'devws = devws.cli.main:devws',
        ],
    },
    description='A comprehensive CLI for Linux Development Environment Setup and Workstation Synchronization.',
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License', # Assuming MIT License
        'Operating System :: POSIX :: Linux',
        'Environment :: Console',
    ],
    python_requires='>=3.7',
)
