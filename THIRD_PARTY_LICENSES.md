# Third-Party Licenses

SynTara (HackDataV2) depends on the packages listed below.
Each entry shows the package, version pinned in `requirements.txt`, its declared license,
and a link to the upstream project for verification.

> **Note:** All models are served through the Groq Cloud API.
> Model license details are in the Models section of `README.md`.

---

## Runtime Dependencies

| Package | Version | License | Project URL |
|---------|---------|---------|-------------|
| fastapi | 0.115.0 | MIT | https://github.com/fastapi/fastapi |
| uvicorn | 0.30.6 | BSD 3-Clause | https://github.com/encode/uvicorn |
| python-multipart | 0.0.9 | Apache 2.0 | https://github.com/Kludex/python-multipart |
| pydantic | 2.8.2 | MIT | https://github.com/pydantic/pydantic |
| simpleeval | 0.9.13 | MIT | https://github.com/danthedeckie/simpleeval |
| pandas | 2.2.2 | BSD 3-Clause | https://github.com/pandas-dev/pandas |
| numpy | 1.26.4 | BSD 3-Clause | https://github.com/numpy/numpy |
| scipy | 1.13.1 | BSD 3-Clause | https://github.com/scipy/scipy |
| scikit-learn | 1.5.1 | BSD 3-Clause | https://github.com/scikit-learn/scikit-learn |
| faker | 26.1.0 | MIT | https://github.com/joke2k/faker |
| jinja2 | 3.1.4 | BSD 3-Clause | https://github.com/pallets/jinja |
| playwright | 1.46.0 | Apache 2.0 | https://github.com/microsoft/playwright-python |
| httpx | 0.27.0 | BSD 3-Clause | https://github.com/encode/httpx |
| groq | 0.13.1 | Apache 2.0 | https://github.com/groq/groq-python |
| python-dotenv | 1.0.1 | BSD 3-Clause | https://github.com/theskumar/python-dotenv |
| pyyaml | 6.0.2 | MIT | https://github.com/yaml/pyyaml |
| dill | 0.3.8 | BSD 3-Clause | https://github.com/uqfoundation/dill |
| babel | 2.15.0 | BSD 3-Clause | https://github.com/python-babel/babel |
| setuptools | 72.1.0 | MIT | https://github.com/pypa/setuptools |
| reportlab | 5.0.0 | BSD 3-Clause | https://www.reportlab.com/dev/opensource/ |
| typesafe-sdk | (unpinned) | Proprietary | https://typesafe.ai |

## Development Dependencies

| Package | Version | License | Project URL |
|---------|---------|---------|-------------|
| pytest | 8.3.2 | MIT | https://github.com/pytest-dev/pytest |
| pytest-cov | 5.0.0 | MIT | https://github.com/pytest-dev/pytest-cov |
| ruff | 0.5.7 | MIT | https://github.com/astral-sh/ruff |

## License Texts

Full license texts are available from each upstream project linked above.
The licenses referenced are:

- **MIT License** — permissive, attribution required
- **BSD 3-Clause License** — permissive, no endorsement clause
- **Apache License 2.0** — permissive, patent grant included
- **Proprietary (typesafe-sdk)** — commercial SDK from TypeSafe AI; usage governed by their terms of service at https://typesafe.ai

---

*Generated 2026-10-01. Re-run `pip show <package>` to verify license text for any entry.*
