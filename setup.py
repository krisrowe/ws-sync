from setuptools import setup, find_packages

setup(
    name='devws',
    version='0.1.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'Click',
        'PyYAML',
        'google-cloud-secret-manager', # Runtime dependency for secrets commands
    ],
    extras_require={
        'tests': [
            'pytest',
            'pytest-mock',
        ],
    },
    entry_points={
        'console_scripts': [
            'devws = devws_cli.cli:devws',
        ],
    },
    author='Your Name', # Replace with actual author
    author_email='your.email@example.com', # Replace with actual email
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
