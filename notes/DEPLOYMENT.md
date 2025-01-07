# How to deploy Aipress24?

## In the cloud

Aipress24 is a "12 Factor" application that can be deployed to many cloud platforms.

### Set up the environment

You will need to set the following environment variables:

#### Mandatory variables

- `DATABASE_URL`: set by the plafform, or to set manually if you are managing the connection to the database yourself.
- `DRAMATIC_REDIS_URL`: needed for the Dramatiq task queue. Should be set to the same value as `REDISCLOUD_URL` (FIXME: this should be done automatically).
- `FLASK_RQ_REDIS_URL`: same remark as for `DRAMATIC_REDIS_URL`.
- `REDISCLOUD_URL`: see above.

- `FLASK_SERVER_NAME`: the domain name for the application.
- `FLASK_SECRET_KEY`: a secret key for the Flask application. Should be a long random string.
- `FLASK_SECURITY_PASSWORD_SALT`: a salt for the Flask-Security password hashing. Should be a long random string.
- `FLASK_MAIL_SERVER`: the SMTP server used to send emails.
- `FLASK_MAIL_PORT`: the port for the SMTP server.
- `FLASK_MAIL_USE_TLS`: set to `True` if the SMTP server uses TLS.
- `FLASK_MAIL_USERNAME`: the email account used to send emails.
- `FLASK_MAIL_PASSWORD`: the password for the email account used to send emails.
- `FLASK_MAIL_DEFAULT_SENDER`: the default sender address for emails.

- `PYTHONPATH`: should be set to `src` to allow the application to find the source code, on some platforms like Heroku (don't ask me why).

#### Optional variables

- `FLASK_SENTRY_DSN`: the DSN for Sentry error tracking (if you are using Sentry).
- `FLASK_STRIPE_API_KEY`: the API key for the Stripe payment gateway (if you are using Stripe).
- `FLASK_STRIPE_PUBLIC_KEY`: the public key for the Stripe payment gateway (if you are using Stripe).
- `FLASK_STRIPE_SECRET_KEY`: the secret key for the Stripe payment gateway (if you are using Stripe).
- `HYPERDX_API_KEY`: the API key for the HyperDX API (if you are using HyperDX).
- `OTEL_SERVICE_NAME`: the name of the service for OpenTelemetry tracing.

### Heroku

Create a project on Heroku and deploy the application using the Heroku CLI.

The `Procfile` is already configured to run the application.

You will need to set some of the environment variables listed above (not those set by the platform), using either the Heroku CLI or the Heroku dashboard.

### Fly.io

Create a project on Fly.io and deploy the application using the `fly` CLI.

A `fly.toml` configuration file is provided in the repository, but you might need to tweak it.

The `Procfile` is not used by Fly.io.

You will need to set some of the environment variables listed above (not those set by the platform), using either the `fly` CLI or the Fly.io dashboard.

### Clever Cloud

Same as above. We had a working deployment on Clever Cloud, but it was a while ago and the configuration might have changed.

### Hop3

This is a work in progress. We are working on a deployment to Hop3, a new cloud platform that is still in beta.

For experimental deployments, using sqlite as the database (instead of PostgreSQL, as recommended for production):

For experimental deployment to [Hop3](https://hop3.cloud/), you can use shell commands similar to the following:

```bash
export HOP3="YOUR_HOP3_HOST"
export HOSTNAME="aipress24.YOUR_DOMAIN"
# 1. Push SQLite database to
scp data/aipress24.db root@$HOP3:~hop3/data/aipress24/
# + run `chown hop3:www-data /home/hop3/data/aipress24/aipress24.db` on the server
# 2. Only once
git remote add hop3 hop3@$HOP3:aipress24
# 3. Deploy
git push hop3 main
# 4. Needed only once
hop config:set NGINX_SERVER_NAME=$HOSTNAME
hop config:set FLASK_SQLALCHEMY_DATABASE_URI=sqlite:////home/hop3/data/aipress24/aipress24.db
# Additional environment variables will be needed
```

### Other platforms

Aipress24 is a standard Flask application that can be deployed to many cloud platforms. You will need to set up a PostgreSQL database, a Redis instance, and a SMTP server.

## On-premises

You may also deploy Aipress24 on your own servers.

You will need to set up a PostgreSQL database, a Redis instance, and a SMTP server.

You will need to set the environment variables listed above, using either a `.env` file or a mechanism provided by your process manager (e.g. `systemd`, `supervisord`, `uwsgi`, etc.).

You will probably need to set a reverse proxy like `nginx` or `traefik`, and manage your SSL certificates (possibly using `certbot`).

