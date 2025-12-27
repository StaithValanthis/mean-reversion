"""Setup script for mean-reversion trading bot."""
from setuptools import find_packages, setup

setup(
    name="mean-reversion-bot",
    version="1.0.0",
    description="Mean reversion trading bot for Bybit",
    packages=find_packages(),
    install_requires=[
        "python-dateutil>=2.8.2",
        "pytz>=2024.1",
        "numpy>=1.24.0",
        "pandas>=2.0.0",
        "pyyaml>=6.0",
        "ccxt>=4.0.0",
        "pyarrow>=12.0.0",
        "python-dotenv>=1.0.0",
    ],
    python_requires=">=3.11",
)

