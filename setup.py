from setuptools import setup, find_packages

with open("Readme.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()
    
setup(
    name="watchman-agent-client",
    version="1.0.0",
    author="Watchman",
    author_email="support@watchman.bj",
    # description = "Watchman Agent 1.0.0",
    description='Agent pour collecter des informations système et les envoyer à une API centrale.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    include_package_data=True,
    packages=find_packages(),
    python_requires='>=3.8',
    install_requires=[
        "psutil>=5.9.0 ",
        "requests>=2.28.0",
        "Flask>=2.3.0 ",
        "schedule>=1.2.0",
        "configparser>=5.3.0",
        "pywin32>=306; platform_system=='Windows'",
        "pytest>=7.0.0",
        "pytest-cov>=4.0.0",
        "black>=23.0.0",
        "flake8>=6.0.0",
    ],

    entry_points='''
        [console_scripts]
        watchman-agent-client=agent.main:main
    '''
)
