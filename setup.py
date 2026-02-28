from setuptools import setup, find_packages

setup(
    name="dependency-inspector-mcp",
    version="0.1.0",
    description="Deterministic MCP server for dependency and license inspection, policy compliance, and SBOM generation",
    author="MCP Dependency Inspector Team",
    python_requires=">=3.11",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "fastmcp>=2.3.0",
        "mcp>=1.6.0",
        "httpx>=0.27.0",
        "tenacity>=8.2.3",
        "tomli>=2.0.1",
        "ruamel.yaml>=0.18.6",
        "packaging>=24.0",
        "pydantic>=2.7.0",
        "pydantic-settings>=2.3.0",
        "license-expression>=30.3.1",
        "python-dotenv>=1.0.1",
    ],
    entry_points={
        "console_scripts": [
            "dependency-inspector-mcp=mcp_dependency_inspector.server:main",
        ],
    },
)
