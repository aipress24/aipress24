# Aipress24

Welcome to the Aipress24 project! Aipress24 is an innovative, open-source digital platform designed to transform the way journalists, news agencies, and media professionals collaborate and monetize their work. Developed by [Techno-Chroniqueurs Associés](https://agencetca.info/), with the technical expertise of Abilian, Aipress24 provide a comprehensive B2B environment tailored to the needs of the information and innovation sectors.

> [!WARNING]
> This code is still evolving quickly, and not meant for production yet.
> In particular, the database schema is still evolving, and we don't support schema migrations yet.

## Table of Contents

<!-- toc -->

- [Introduction](#introduction)
- [Features](#features)
- [Getting Started / Installation](#getting-started--installation)
  * [Development](#development)
  * [Third party libraries & services](#third-party-libraries--services)
  * [Testing](#testing)
- [Contributing](#contributing)
  * [Development Environment](#development-environment)
  * [Tooling](#tooling)
  * [Contribution Guidelines](#contribution-guidelines)
  * [Code Style](#code-style)
  * [Testing](#testing-1)
    + [`pytest`](#pytest)
  * [Documentation](#documentation)
  * [Pull Request Process](#pull-request-process)
  * [Code of Conduct](#code-of-conduct)
  * [Architecture](#architecture)
  * [Tentative Roadmap](#tentative-roadmap)
    + [Q4 2024](#q4-2024)
    + [Q1 2025](#q1-2025)
    + [Q2 2025](#q2-2025)
    + [Q3 2025](#q3-2025)
    + [Q4 2025](#q4-2025)
    + [S1 2026](#s1-2026)
    + [S2 2026](#s2-2026)
  * [Community](#community)
- [License](#license)
- [Technology used](#technology-used)
  * [Back-end](#back-end)
  * [AI](#ai)
  * [Front-end](#front-end)
  * [Build / dev tools](#build--dev-tools)
- [Security](#security)
- [Deployment](#deployment)
  * [Deploy to Heroku](#deploy-to-heroku)
  * [Deploy to Hop3](#deploy-to-hop3)

<!-- tocstop -->

Additionals notes:

- [CODE_OF_CONDUCT.md](notes/CODE_OF_CONDUCT.md) - Code of Conduct
- [TROUBLESHOOTING.md](notes/TROUBLESHOOTING.md) - Troubleshooting guide
- [PUBLIC_CODE_COMPLIANCE.md](notes/PUBLIC_CODE_COMPLIANCE.md) - Public Code Compliance self-assessment
- [STANDARDS.md](notes/STANDARDS.md) - Standards used by Aipress24
- [CHANGELOG.md](notes/CHANGELOG.md) - Changelog
- [CITATION.cff](notes/CITATIONS.cff) - Citation file
- [DCO.txt](notes/DCO.txt) - Developer Certificate of Origin
- [DEPLOYMENT.md](notes/DEPLOYMENT.md) - Deployment instructions (on cloud platforms or on-premises)

See also the companion documentation <https://doc.aipress24.com/> and its source, the documentation repository: <https://github.com/aipress24/aipress24-doc>.

## Introduction

Aipress24 aims to revolutionize the media industry by offering a suite of tools that enhance productivity, foster community interaction, and create new revenue streams for journalists and media organizations. Our mission is to support journalism and innovation by providing a platform that facilitates content creation, collaboration, and distribution.

## Features

- **Collaborative Newsroom**: A digital workspace where journalists can create, edit, and publish content
  collaboratively.
- **Professional Social Network**: Connect with other media professionals, share insights, and build your network.
- **Marketplace**: Sell and purchase editorial products and services, including articles, reports, and multimedia
  content.
- **Content Management**: Advanced tools for managing articles, press releases, event schedules, and more.
- **Event Scheduling**: Organize and manage media events, press conferences, and interviews.
- **Reputational Performance Index (IRP)**: Evaluate journalists based on their interactions and contributions.
- **Secure and Transparent**: Ensures secure transactions and interactions with rigorous verification of professionals.

## Getting Started / Installation

### Development

Assuming you have Python (version 3.12 or 3.13) and `poetry` installed, to get started with Aipress24, follow these
steps:

1. **Clone the Repository**:
    ```bash
    git clone https://github.com/aipress24/aipress24.git
    ```
2. **Install Dependencies**:
   Navigate to the project directory and install the necessary dependencies.
    ```bash
    cd aipress24
    poetry shell
    make develop
    ```
3. **Set environment variables**:
    ```bash
    cp .env.sample .env
    ```
   And then edit `.env` to set the environment variables to your liking.
3. **Create fake data**:
    ```bash
    make fake
    ```
4. **Run the Application**:
   Start the development server.
    ```bash
    make run
    ```
5. **Open Your Browser**:
   Open your browser and go to `http://localhost:5000` to see the application in action.

### Third party libraries & services

- PostgreSQL
- Redis
- Typesense

To start Typesense (currently):

```
docker run -p 8108:8108 -v/srv/typesense-server-data-1c/:/data -d typesense/typesense:0.23.1 --data-dir /data --api-key=<key> --listen-port 8108 --enable-cors
```

### Testing

- Testing + static checking:

```bash
poetry install
poetry run make lint
poetry run make test-sqlite
poetry run nox
```

## Contributing

We welcome contributions from the community! Whether you're a developer, designer, journalist, or simply someone
passionate about media and innovation, there are many ways to get involved:

- **Submit Issues**: If you find bugs or have feature requests, please submit an issue on our GitHub repository [issue tracker](https://github.com/aipress24/aipress24/issues).
- **Fork the Repository**: Make changes in your own fork, and submit a pull request when you're ready.
- **Join Discussions**: Participate in discussions on our [forums](https://github.com/aipress24/aipress24/discussions) or GitHub [issues](https://github.com/aipress24/aipress24/issues) to help shape the future of Aipress24.
- **Documentation**: Help improve our documentation by contributing to this README, the [notes](https://github.com/aipress24/aipress24/tree/main/notes) or the [documentation](https://github.com/aipress24/aipress24-doc).

### Development Environment

Okay, here's the revised "Development Environment" section, incorporating your feedback and focusing on the Python (with some NodeJS) nature of the application:

### Development Environment

To set up your development environment for this primarily Python-based application, with some Node.js components for the frontend, ensure you have the following installed:

-   **Python**: Version 3.12 or 3.13.
-   **Poetry**: For managing Python dependencies and virtual environments.
-   **Node.js**: We recommend using the latest LTS version for frontend development.
-   **npm** or **Yarn** **Bun**: To manage Node.js packages.

Once you have these installed, follow these steps to set up your development environment:

1. **Clone the Repository**: Clone the repository to your local machine using Git:

    ```bash
    git clone ...
    ```

2. Type `make develop` to install the necessary dependencies and set up the development environment.


### Tooling

Besides the `uv` tool, we use the following tools to maintain the codebase:

- **ruff**: A modern, flexible, and efficient way to manage Python environments.
- **black**: The uncompromising Python code formatter.
- **isort**: A Python utility / library to sort imports.
- **flake8**: A Python tool that glues together pep8, pyflakes, mccabe, and third-party plugins to check the style and quality of some Python code.
- **mypy**: An optional static type checker for Python.
- **pyright**: A static type checker for Python that runs in the background.
- **pytest**: A framework that makes it easy to write small tests, yet scales to support complex functional testing for applications and libraries.
- **beartype**: A runtime type-checker for Python functions.
- **typeguard**: Run-time type checking for Python functions.
- **nox**: A flexible test automation tool that automates testing in multiple Python environments.

We orchestrate these tools using `make`, the standard build tool on Unix-like systems, which provides shortcuts for common tasks based on these tools:

The provided `Makefile` orchestrates various tasks to streamline development, testing, formatting, and maintenance workflows. Here’s a high-level overview of the key functionalities it provides:

- **`develop`**: Installs development dependencies, activates pre-commit hooks, and configures Git for rebase workflows by default.
- **`install-deps`**: Ensures the project's dependencies are synced and up-to-date using `uv sync`.
- **`update-deps`**: Updates the project's dependencies to the latest compatible versions using `uv sync -U`.
- **`activate-pre-commit`**: Installs pre-commit hooks to automatically enforce coding standards during commits.
- **`configure-git`**: Sets Git to use rebase workflows automatically when pulling branches.
- **`test`**: Runs Python unit tests using `pytest`.
- **`test-randomly`**: Executes tests in a randomized order to uncover order-dependent issues.
- **`test-e2e`**: Placeholder for running end-to-end tests (not yet implemented).
- **`test-with-coverage`**: Runs tests and generates a coverage report for the specified package.
- **`test-with-typeguard`**: Verifies runtime type checking for the package using `Typeguard`.
- **`lint`**: Performs linting and type-checking using `adt check` to ensure code quality.
- **`format`**: Formats code to meet the style guide using `docformatter` for documentation strings and `adt format` for general formatting.
- **`clean`**: Cleans up temporary files, cache directories, and build artifacts, leaving the repository in a pristine state.
- **`help`**: Displays available `make` commands and their descriptions, leveraging `adt help-make`.

The full list of available commands can be viewed by running `make help`.


### Contribution Guidelines

1. **Fork the Repository**: Create a fork of the repository in your own GitHub/GitLab account.
2. **Create a Feature Branch**: Make a new branch in your fork for the feature or bugfix you plan to work on.
3. **Follow the Code Style**: Adhere to the project's code style guidelines (see below).
4. **Add Tests**: Ensure your changes are covered by appropriate unit and integration tests.
5. **Document Changes**: Update relevant sections in the documentation, including this README if necessary.
6. **Submit a Pull Request**: Open a pull request against the `main` branch of this repository with a clear description of your changes.

### Code Style

We use **PEP 8** as the basis for our code style. In practice, most of the code formatting is handled by the following tools:

- **Ruff**: Does most of the formatting, and also handles linting and static analysis.
- **Black**: Ensures consistent formatting (currently phased out in favor of `ruff`).
- **isort**: Organizes imports (currently phased out in favor of `ruff`).
- **Pyupgrade**: Upgrades syntax to newer versions of Python.

To apply formatting and linting, simply run:

```bash
black .
isort .
ruff format
ruff . --fix
```

(`ruff` last as it may conflict with some of the changes made by `black` and `isort`.)

Or, better yet, use the provided `Makefile` shortcuts:

- `make format`: Apply formatting.

### Testing

Tests are critical to maintaining the quality and reliability of the codebase. We encourage contributors to:

- Add **unit tests** for new or modified functionalities.
- Write **integration tests** for changes that affect multiple components.


#### `pytest`

Run all tests using:

```bash
pytest
```

For test coverage, use:

```bash
pytest --cov=aipress24
```

The `Makefile` provides shortcuts for common testing tasks:

- `make test`: Run all tests.
- `make test-randomly`: Run tests in random order.
- `make test-with-coverage`: Run tests with coverage report.
- `make test-with-typeguard`: Run tests with typeguard enabled.
- `make test-with-beartype`: Run tests with beartype enabled.
- `make lint`: Run linters and static analysis.

### Documentation

All new features or changes should be documented. The documentation should include:

- **Code Comments**: Explain non-trivial parts of the code.
- **README Updates**: Update this file for any major changes in functionality or usage.
- **Changelog**: Add a note in the upcoming changelog (to be implemented).

### Pull Request Process

To ensure a smooth review process:

1. Make sure your branch is **up to date** with the `main` branch.
2. Ensure all tests pass and there are no linting or formatting issues.
3. Provide a clear and concise description of the changes in your pull request, including any relevant issue numbers.
4. Be responsive to reviewer feedback and address any requested changes promptly.


### Code of Conduct

This project adheres to the [PSF Code of Conduct](https://policies.python.org/python.org/code-of-conduct/). By participating, you agree to abide by its terms. Please be respectful and collaborative in all interactions.

For further details, see the `[CODE_OF_CONDUCT.md](notes/CODE_OF_CONDUCT.md)` file in the repository.

### Architecture

Aipress24 is built using modern web technologies to ensure scalability, security, and performance:

- **Frontend**: Developed using HTMX and TailwindCSS for a responsive and interactive user interface.
- **Backend**: Powered by Python, with a PostgreSQL database for data management.
- **Search**: Utilizes ElasticSearch for powerful and efficient search capabilities.
- **Storage**: Amazon S3 compatible open-source solutions like Minio or Ceph for object storage.
- **Security**: Implements best practices for security, including bcrypt for password hashing and proactive monitoring.

For more details, see: <https://doc.aipress24.com/dev/architecture/>

### Tentative Roadmap

#### Q4 2024

0. **Update Documentation**
    - Update the documentation to reflect the latest changes and features.
    - See: README, notes, <https://doc.aipress24.com/>
1. **Finalize Core Platform Stabilization**
    - Refactor and stabilize the data model to ensure compatibility with future updates.
2. **News Portal MVP**
    - Launch the news portal with basic features for publishing, viewing, and ranking articles.
3. **Social Interaction Features**
    - Deploy Like, Share, and Comment functionality with customizable settings for authors.
    - Implement metrics for content popularity and interaction (e.g., views, shares, purchases).
4. **Business Wall Subscriptions**
    - Complete Business Wall subscription system for PR professionals, organizations, and media.

#### Q1 2025

1. **Marketplace for Journalists**
    - Launch a marketplace for selling articles, multimedia content, and intellectual property licenses.
2. **Content Management Tools**
    - Add advanced tools for categorizing, tagging, and managing articles.
    - Enable bulk publishing and scheduling for agencies.
3. **Matchmaking System**
    - Develop ML-driven matchmaking for connecting journalists, PR professionals, and experts.
    - Allow filters for specific sectors, regions, or topics.
4. **ERP Integration**
    - Integrate Dolibarr ERP for managing organizational finances. Cf. <https://doc.aipress24.com/dev/dolibarr/>.
5. **Cloud Deployment**
    - Package as a Nix / NixOS application for easy deployment on cloud platforms.
    - Support deployment on Hop3.
    - Refactor blob storage to support S3-compatible solutions.

#### Q2 2025

1. **Reputational Performance Index (IRP)**
    - Introduce IRP to measure journalist contributions based on metrics like engagement and content quality.
    - Provide organization-specific IRP settings to customize evaluation criteria.
2. **ActivityPub Integration**
    - Begin pilot integration with ActivityPub to enable federated content sharing across instances.
    - Build connectors for interoperability with Mastodon, Mobilizon, and other platforms.
3. **Press and Media Tools**
    - Develop advanced analytics for organizations to track content performance and audience reach.
    - Launch tools for submitting requests for interviews or expert commentary.
4. **Improved Payment System for the Marketplace**
    - Integrate GNU Taler for secure micropayments and wallet management.

#### Q3 2025

1. **Federation Architecture**
    - Establish framework for hosting multiple instances of AIpress24.
    - Define governance models for federated instances to ensure interoperability.
2. **Personalized RSS Feeds**
    - Enable users to generate personalized RSS feeds for curated content distribution.
3. **Advanced Security Features**
    - Implement data encryption for sensitive information and enhance user role management.
    - Develop GDPR-compliant privacy settings for data storage and sharing.

#### Q4 2025

1. **AI-Powered Content Insights**
    - Deploy AI tools to provide trend analysis, topic suggestions, and content recommendations.
    - Implement NLP-based tools for summary generation and keyword extraction.
2. **Enhanced Marketplace Features**
    - Launch custom workflows for agencies managing large volumes of content.
    - Introduce modules for pricing and payment tracking with GNU Taler.
3. **Custom API for Third-Party Tools**
    - Release API endpoints for integrating external tools (e.g., newsroom software, analytics platforms).

#### S1 2026

1. **Certification and Badging**
    - Implement “Source Agency” and “Certified Author” badges to verify content authenticity.
    - Align certifications with Journalism Trust Initiative (JTI) standards.
2. **Multimedia Content Expansion**
    - Introduce support for podcasts, video content, and interactive visualizations.
    - Enable monetization and licensing of multimedia formats on the marketplace.
3. **Event Scheduling Module**
    - Launch event tools for managing press conferences, interviews, and live streams.
4. **Federated Governance**
    - Formalize federated governance structure, with committees for ethics, development, and community feedback.
    - Develop dashboards for instance administrators to monitor performance and compliance.
5. **Localization and Regional Adaptations**
    - Roll out support for multilingual interfaces and localized content recommendations.
    - Deploy region-specific adaptations of payment systems, including GNU Taler integrations.

#### S2 2026

1. **Global Scaling**
    - Support the creation and management of new federated instances in key global regions.
    - Develop automated tools for onboarding local administrators and partners.
2. **Open Plugin Ecosystem**
    - Introduce plugin support for extending platform features, based on frameworks like Pluggy.
    - Provide SDK and documentation for developers to create custom extensions.
3. **Advanced Analytics and Reporting**
    - Enable organizations to generate detailed reports on engagement, financial performance, and IRP metrics.
4. **Full ActivityPub Integration**
    - Complete integration of ActivityPub for seamless inter-instance and inter-platform content sharing.
5. **Social Graph and Networking**
    - Build a professional social graph for networking between journalists, PR professionals, and organizations.
    - Add tools for tracking professional connections and collaboration history.
6. **Accessibility Improvements**
    - Enhance accessibility features, including WCAG-compliant UI improvements.


### Community

Join our growing community of contributors and users! Stay updated and participate in discussions:

- **Discussions**: Participate in discussions on our GitHub repository and share your feedback, or join the
  Aipress24.com community as a "Transformer" (when the platform is open).
- **Meetups**: Attend our virtual meetups and webinars to learn more about Aipress24 and how you can contribute.

## License

Aipress24 is licensed under the AGPL-3.0 License, except for vendored code.
See the [LICENSE](LICENSE) file for more information.

Here is the REUSE summary as of 2024/06/17:

> * Bad licenses: 0
> * Deprecated licenses: 0
    >
* Licenses without file extension: 0
> * Missing licenses: 0
> * Unused licenses: 0
> * Used licenses: MIT, LicenseRef-ARR, ISC, AGPL-3.0-only
> * Read errors: 0
> * files with copyright information: 2363 / 2363
> * files with license information: 2363 / 2363
>
> Congratulations! Your project is compliant with version 3.0 of the REUSE Specification :-)

## Technology used

### Back-end

- [Flask](https://flask.palletsprojects.com/)
- [RQ](https://python-rq.org/) -> Actually, replaced by [Dramatiq](https://dramatiq.io)
- [SQLAlchemy](https://sqlalchemy.org)
- [Typesense](https://typesense.org)
- [Redis](https://redis.io)
- [PostgreSQL](https://www.postgresql.org)

### AI

- [Scikit-learn](https://scikit-learn.org/)
- [Spacy](https://spacy.io/)
- And also: Gensim, NLTK, Pandas, etc.

### Front-end

- [TailwindCSS](https://tailwindcss.com)
- [AlpineJS](https://alpinejs.dev)
- [HTMX](https://htmx.org/)
- [HTML5 platform](https://platform.html5.org)

### Build / dev tools

- [Poetry](https://python-poetry.org)
- [Abilian Dev Tools](https://pypi.org/project/abilian-devtools/)
- [Nox](https://nox.thea.codes/)
- [Vite](https://vitejs.dev)

## Security

Before going into production, you should run:

```shell
# Assuming APP_ROOT_URL = URL of a demo or local instance
adt audit
docker run --rm secscan/nikto -h $APP_ROOT_URL
```

## Deployment

See [DEPLOYMENT.md](notes/DEPLOYMENT.md) for deployment instructions on cloud platforms or on-premises.

Older instrustions are below.

### Deploy to Heroku (old instructions, TODO: update)

To deploy Aipress24 to Heroku, you can use the following commands:

```bash
heroku create my-aipress24 # Use your own app name
heroku addons:create heroku-postgresql:essential-0
heroku addons:create heroku-redis:mini
# heroku addons:create typesense:free # Not yet available
heroku config:set FLASK_APP=aipress24
heroku config:set FLASK_ENV=production
heroku config:set FLASK_SECRET_KEY=$(openssl rand -hex 16)
heroku config:set FLASK_SQLALCHEMY_DATABASE_URI=$(heroku config:get DATABASE_URL)
heroku config:set FLASK_REDIS_URL=$(heroku config:get REDIS_URL)
# heroku config:set FLASK_TYPESENSE_URL=$(heroku config:get TYPESENSE_URL)
# heroku config:set FLASK_TYPESENSE_KEY=$(heroku config:get TYPESENSE_KEY)
heroku config:set FLASK_MAIL_SERVER=smtp.sendgrid.net
heroku config:set FLASK_MAIL_PORT=587
heroku config:set FLASK_MAIL_USE_TLS=1
heroku config:set FLASK_MAIL_USERNAME=apikey
heroku config:set FLASK_MAIL_PASSWORD=YOUR_SENDGRID_API_KEY
heroku config:set FLASK_MAIL_DEFAULT_SENDER=YOUR_SENDGRID_EMAIL
```

---

Thank you for your interest in Aipress24! We are excited to have you join our mission to support journalism and
innovation through open-source technology. If you have any questions or need further assistance, please feel free to
reach out to us through our community channels.
