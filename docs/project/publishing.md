# Publishing

Two artifacts are published from this repository: the documentation site on
GitHub Pages, and the package on PyPI.

## Documentation

The Material site is published to GitHub Pages at
[open-byte.github.io/django-modern-schemas](https://open-byte.github.io/django-modern-schemas/).

### One-Time Repository Setup

An organization owner or repository administrator must enable GitHub Pages once:

1. Open the repository **Settings**.
2. Open **Pages** in the sidebar.
3. Under **Build and deployment**, choose **GitHub Actions** as the source.

The deployment workflow then has the permissions it needs to publish the built
site.

### Automatic Deployment

[`deploy-docs.yml`](https://github.com/open-byte/django-modern-schemas/blob/main/.github/workflows/deploy-docs.yml)
deploys after a push to `main` that changes documentation, executable examples,
the Material configuration, or documentation dependencies.

The workflow:

1. Installs the locked `docs` dependency group with `uv`.
2. Runs `mkdocs build --strict`.
3. Uploads the generated `site/` directory to GitHub Pages.

The deployment URL appears in the **Deploy Documentation** workflow summary.

### Manual Deployment

Open the repository **Actions** tab, choose **Deploy Documentation**, and select
**Run workflow**. This is useful when Pages has just been enabled or when a
deployment must be repeated without another documentation commit.

### Local Verification

Build the same artifact before pushing:

```bash
uv sync --group docs
uv run --group docs mkdocs build --strict
```

Preview it locally with:

```bash
uv run --group docs mkdocs serve
```

## Package

The package is published to
[pypi.org/project/django-modern-schemas](https://pypi.org/project/django-modern-schemas/)
and built with the `uv_build` backend. The version lives in exactly one place,
`pyproject.toml`; `django_modern_schemas.__version__` reads it back from the
installed distribution metadata.

### One-Time PyPI Setup

Releases upload through
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/), so no API token
is stored in the repository. An owner configures the publisher once with these
values:

| Field | Value |
| --- | --- |
| PyPI Project Name | `django-modern-schemas` |
| Owner | `open-byte` |
| Repository | `django-modern-schemas` |
| Workflow | `publish.yml` |
| Environment | `pypi` |

Where that form lives depends on whether the project already exists on PyPI:

- **Before the first release**, the project has no settings page yet, so it is
  registered as a *pending* publisher at
  [Account settings → Publishing](https://pypi.org/manage/account/publishing/).
  PyPI creates the project on the first successful upload and converts the
  pending publisher into a normal one.
- **Afterwards**, at **Manage project → Publishing**.

The GitHub `pypi` environment must also exist, under **Settings → Environments**
in the repository. It can be empty; the workflow only needs the name to match.

### Cutting a Release

```bash
uv version --bump minor      # or --bump patch / --bump major
uv lock                      # the lock records the project version too
```

Commit the result, merge it to `main`, then tag and publish a GitHub Release
whose tag is the version prefixed with `v` (`v0.1.0` for `0.1.0`):

```bash
git tag v0.1.0
git push origin v0.1.0
```

Publishing the release triggers
[`publish.yml`](https://github.com/open-byte/django-modern-schemas/blob/main/.github/workflows/publish.yml),
which refuses to continue when the tag and the packaged version disagree, then
builds, validates the metadata with `twine check`, and uploads.

### Local Verification

Build and inspect the artifacts without uploading anything:

```bash
make build
uv run --with twine twine check dist/*
```

To rehearse the upload end to end, publish to
[TestPyPI](https://test.pypi.org/) first — a separate site with its own account
and token:

```bash
UV_PUBLISH_TOKEN='pypi-...' make publish-test
```

Then install from there into a throwaway environment. TestPyPI has no usable
Django or Pydantic, so PyPI stays the primary index and TestPyPI is added as an
extra. `--index-strategy unsafe-best-match` is required: under the default
`first-index` strategy uv stops at the first index it consults and never falls
through to the one holding the release candidate.

```bash
uv venv /tmp/dms-smoke
VIRTUAL_ENV=/tmp/dms-smoke uv pip install \
  --index-strategy unsafe-best-match \
  --index-url https://pypi.org/simple/ \
  --extra-index-url https://test.pypi.org/simple/ \
  django-modern-schemas
```

### Supported Versions

Every version the package advertises is executed by the `compat` job in
[`test_full.yml`](https://github.com/open-byte/django-modern-schemas/blob/main/.github/workflows/test_full.yml),
which pins Django and Pydantic instead of resolving from the lock. When a floor
in `pyproject.toml` changes, add or move a cell in that matrix so the claim stays
tested.

`requires-python` is uncapped. Python 3.14 needed the schema metaclass to change
how it reads a class body: [PEP 649](https://peps.python.org/pep-0649/) defers the
evaluation of class annotations, so `__annotations__` is no longer sitting in the
namespace and reading it returned nothing — silently dropping every declared
`Source` and `MethodSource` field. The metaclass now goes through
[`annotationlib`](https://docs.python.org/3.14/library/annotationlib.html)
instead, and drops the `__annotate_func__` the body left behind once it has
written the fields it computed.