# AIPress24

Welcome to the AIpress24 project! AIpress24 is an innovative, open-source digital platform designed to transform the way journalists, news agencies, and media professionals collaborate and monetize their work. Developed by Techno-Chroniqueurs Associés, with the technical expertise of Abilian, AIpress24 provides a comprehensive B2B environment tailored to the needs of the information and innovation sectors.

> [!WARNING]
> This code is still evolving quickly, and not meant for production yet.
> In particular, the database schema is still evolving, and we don't support schema migrations yet.

## Table of Contents

- [Introduction](#introduction)
- [Features](#features)
- [Getting Started](#getting-started)
- [Contributing](#contributing)
- [Architecture](#architecture)
- [Community](#community)
- [License](#license)

## Introduction

AIpress24 aims to revolutionize the media industry by offering a suite of tools that enhance productivity, foster community interaction, and create new revenue streams for journalists and media organizations. Our mission is to support journalism and innovation by providing a platform that facilitates content creation, collaboration, and distribution.

## Features

- **Collaborative Newsroom**: A digital workspace where journalists can create, edit, and publish content collaboratively.
- **Professional Social Network**: Connect with other media professionals, share insights, and build your network.
- **Marketplace**: Sell and purchase editorial products and services, including articles, reports, and multimedia content.
- **Content Management**: Advanced tools for managing articles, press releases, event schedules, and more.
- **Event Scheduling**: Organize and manage media events, press conferences, and interviews.
- **Reputational Performance Index (IRP)**: Evaluate journalists based on their interactions and contributions.
- **Secure and Transparent**: Ensures secure transactions and interactions with rigorous verification of professionals.

## Getting Started / Installation

### Development

Assuming you have Python (version 3.12 or 3.13) and `poetry` installed, to get started with AIpress24, follow these steps:


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
5**Open Your Browser**:
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

We welcome contributions from the community! Whether you're a developer, designer, journalist, or simply someone passionate about media and innovation, there are many ways to get involved:

- **Submit Issues**: If you find bugs or have feature requests, please submit an issue on our GitHub repository.
- **Fork the Repository**: Make changes in your own fork, and submit a pull request when you're ready.
- **Join Discussions**: Participate in discussions on our forums or GitHub issues to help shape the future of AIpress24.
- **Documentation**: Help improve our documentation by contributing to our Wiki or README files.

### Development Environment

To set up your development environment, ensure you have Node.js and npm installed. We recommend using the latest LTS version of Node.js.

1. **Fork the Repository**: Click the "Fork" button at the top of the repository page on GitHub.
2. **Clone Your Fork**: Clone your fork to your local machine.
    ```bash
    git clone https://github.com/aipress24/aipress24.git
    ```
3. **Create a Branch**: Create a new branch for your feature or bugfix.
    ```bash
    git checkout -b feature/your-feature-name
    ```
4. **Make Changes**: Make your changes in your local repository.
5. **Commit Changes**: Commit your changes with a meaningful commit message.
    ```bash
    git commit -m "Add feature: your feature name"
    ```
6. **Push Changes**: Push your changes to your fork on GitHub.
    ```bash
    git push origin feature/your-feature-name
    ```
7. **Create a Pull Request**: Go to the original repository and create a pull request from your fork.

## Architecture

AIpress24 is built using modern web technologies to ensure scalability, security, and performance:

- **Frontend**: Developed using HTMX and TailwindCSS for a responsive and interactive user interface.
- **Backend**: Powered by Python, with a PostgreSQL database for data management.
- **Search**: Utilizes ElasticSearch for powerful and efficient search capabilities.
- **Storage**: Amazon S3 compatible open-source solutions like Minio or Ceph for object storage.
- **Security**: Implements best practices for security, including bcrypt for password hashing and proactive monitoring.

## Community

Join our growing community of contributors and users! Stay updated and participate in discussions:

- **Discussions**: Participate in discussions on our GitHub repository and share your feedback, or join the Aipress24.com community as a "Transformer" (when the platform is open).
- **Meetups**: Attend our virtual meetups and webinars to learn more about AIpress24 and how you can contribute.

## License

AIpress24 is licensed under the AGPL-3.0 License, except for vendored code.
See the [LICENSE](LICENSE) file for more information.

Here is the REUSE summary as of 2024/06/17:

> * Bad licenses: 0
> * Deprecated licenses: 0
>  * Licenses without file extension: 0
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

### Deploy to Hop3

For experimental deployment to Hop3, you can use the following commands:

```bash
export HOP3="YOUR_HOP3_HOST"
export HOSTNAME="aipress24.YOUR_DOMAIN"
# 1. Push SQLite database to
scp data/aipress24.db root@$HOP3:~hop3/data/aipress24/
# + run `chown hop3:www-data /home/hop3/data/aipress24/aipress24.db` on the server
# 2. Only once
git remote add hop3 hop3@$HOP3:aipress24
# 3. Deploy
git push hop3 master
# 4. Needed only once
hop config:set NGINX_SERVER_NAME=$HOSTNAME
hop config:set FLASK_SQLALCHEMY_DATABASE_URI=sqlite:////home/hop3/data/aipress24/aipress24.db
```

---

Thank you for your interest in AIpress24! We are excited to have you join our mission to support journalism and innovation through open-source technology. If you have any questions or need further assistance, please feel free to reach out to us through our community channels.
