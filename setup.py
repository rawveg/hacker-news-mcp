from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="hacker-news-mcp",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A Model Context Protocol (MCP) server for the Hacker News API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/hacker-news-mcp",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "fastmcp>=2.0.0",
        "fastapi>=0.104.0",
        "uvicorn>=0.23.2",
        "httpx>=0.25.0",
        "python-dotenv>=1.0.0",
        "pydantic>=2.4.2",
    ],
    entry_points={
        "console_scripts": [
            "hn-mcp=app.server:main",
        ],
    },
)
