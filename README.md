# mpiperfviewer & mpiperfcli

## Installation

To install `mpiperfcli` or `mpiperfviewer`, download the sdist packages from the [release page](https://github.com/BjarneHa/mpiperfviewer/releases).

For both `mpiperfviewer` and `mpiperfcli`, download [mpiperfcli-0.3.4.tar.gz](https://github.com/BjarneHa/mpiperfviewer/releases/download/0.3.4/mpiperfcli-0.3.4.tar.gz) and [mpiperfviewer-0.3.4.tar.gz](https://github.com/BjarneHa/mpiperfviewer/releases/download/0.3.4/mpiperfviewer-0.3.4.tar.gz), then run:
```bash
$ pip install --user mpiperfcli-0.3.4.tar.gz mpiperfviewer-0.3.4.tar.gz
```

`mpiperfviewer` can then be started using the corresponding command in your shell.
```bash
$ mpiperfviewer
```

For just `mpiperfcli`, download [mpiperfcli-0.3.4.tar.gz](https://github.com/BjarneHa/mpiperfviewer/releases/download/0.3.4/mpiperfcli-0.3.4.tar.gz), then run:
```bash
$ pip install --user mpiperfcli-0.3.4.tar.gz
```

`mpiperfcli` can then be started using the corresponding command in your shell.
```bash
$ mpiperfcli -h
```

**NOTE:** If your system does not allow for globally installed `pip` packages, consider using `pipx` instead. Alternatively, you can just install the package in a venv.

**NOTE:** Remember to add the corresponding folder from `pip` or `pipx` to you `PATH` environment variable.

## Development

`mpiperfviewer` uses [uv](https://docs.astral.sh/uv/getting-started/installation/).
You can install it using your local package manager or simply via:
```bash
$ curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then, you can run `mpiperfviewer` in edit mode using:
```bash
$ uv run mpiperfviewer
```
