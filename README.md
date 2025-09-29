# MPI Performance Analysis

## Installation

To install `mpiperfcli` or `mpiperfviewer`, download the sdist packages from the [release page](https://gitlab.lrz.de/caps-dynamic-systems-research/mpiperfviewer/-/releases/).

For both `mpiperfviewer` and `mpiperfcli`, download [mpiperfviewer-0.3.0.tar.gz](
https://gitlab.lrz.de/caps-dynamic-systems-research/mpiperfviewer/-/jobs/11790123/artifacts/raw/dist/mpiperfviewer-0.3.0.tar.gz?inline=false) and [mpiperfviewer-0.3.0.tar.gz](
https://gitlab.lrz.de/caps-dynamic-systems-research/mpiperfviewer/-/jobs/11790123/artifacts/raw/dist/mpiperfcli-0.3.0.tar.gz?inline=false), then run:
```bash
pip install --user mpiperfcli-0.3.0.tar.gz mpiperfviewer-0.3.0.tar.gz
```

For just `mpiperfcli`, download [mpiperfcli-0.3.0.tar.gz](
https://gitlab.lrz.de/caps-dynamic-systems-research/mpiperfviewer/-/jobs/11790123/artifacts/raw/dist/mpiperfviewer-0.3.0.tar.gz?inline=false), then run:
```bash
pip install --user mpiperfcli-0.3.0.tar.gz
```

**NOTE:** If your system does not allow for globally installed `pip` packages, consider using `pipx` instead. Alternatively, you can just install the package in a venv.

**NOTE:** Remember to add the corresponding folder from `pip` or `pipx` to you `PATH` environment variable.

## Development

`mpiperfviewer` uses [uv](https://docs.astral.sh/uv/getting-started/installation/).
You can install it using or local package manager or simply via:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then, you can run `mpiperfviewer` in edit mode using:
```bash
uv run mpiperfviewer
```
