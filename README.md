# COMP2001

This document explains how to deploy the microservice for this coursework.

## Prepare the database

Before running the service, prepare a SQL Server 2019 or 2022 database and ensure that it is accessible from the machine running the service. The application currently uses the `CW2` schema; the `CW1` scripts are retained as a record of the previous coursework stage.

In SQL Server Management Studio (SSMS), select the target database and use an account with permission to create schemas and their objects. Run the following scripts in order:

1. [CW2_schema.sql](sql/CW2_schema.sql): Create the tables and insert demonstration data.
2. [CW2_views.sql](sql/CW2_views.sql): Create the views.
3. [CW2_procedures.sql](sql/CW2_procedures.sql): Create the stored procedures.
4. [CW2_triggers.sql](sql/CW2_triggers.sql): Create the triggers.

> **Warning:** Running `CW2_schema.sql` again drops and recreates the relevant tables. Existing data in those tables will be lost.

You can also run these scripts with `sqlcmd`. Replace the example server address, database name and login below with your own values. Each command prompts for the database password.

```bash
sqlcmd -S sql.example.com -d TrailApp -U deploy_user -b -I -i sql/CW2_schema.sql
sqlcmd -S sql.example.com -d TrailApp -U deploy_user -b -I -i sql/CW2_views.sql
sqlcmd -S sql.example.com -d TrailApp -U deploy_user -b -I -i sql/CW2_procedures.sql
sqlcmd -S sql.example.com -d TrailApp -U deploy_user -b -I -i sql/CW2_triggers.sql
```

## Run with Docker Compose

Install Docker and the Compose plugin, then open a terminal in the project root. Set `DATABASE_URL` to a SQLAlchemy connection URL for your database. The image includes the `pymssql` driver, so the connection URL should use the `mssql+pymssql` prefix.

The following commands work in Bash and compatible shells:

```bash
export DATABASE_URL='mssql+pymssql://app_user:your_password@sql.example.com:1433/TrailApp'
docker compose up --build -d
```

Once the service is running, open [Swagger UI](http://localhost:8000/docs) to view the interactive API documentation.

### Authentication

The service enables HTTP Basic authentication by default and verifies email addresses and passwords through the following external authentication endpoint:

```text
https://web.socem.plymouth.ac.uk/COMP2001/auth/api/users
```

In Swagger UI, click **Authorize** and enter an email address and password accepted by that authentication service.

Creating a local member profile does not create an account with the external authentication service. When calling `GET /api/v1/members/me`, the email address in the local member profile must match the authenticated email address.

To disable authentication during local development, run:

```bash
export AUTH_ENABLED=false
docker compose up -d
```

With authentication disabled, `/api/v1/members/me` cannot identify the current user and still returns an unauthenticated error. To test member profiles, use the endpoint that retrieves a profile by member ID.

After changing an environment variable, run `docker compose up -d` again so that Compose recreates the container with the updated configuration.

### Stop the service

```bash
docker compose down
```

## Run locally without Docker

Install [uv](https://docs.astral.sh/uv/) and ensure that Python 3.15 is available. Prepare the database as described above, then run the following commands from the project root:

```bash
uv sync --frozen
export DATABASE_URL='mssql+pymssql://app_user:your_password@sql.example.com:1433/TrailApp'
uv run 2001
```

The API listens on `127.0.0.1:8000` by default. To change the listening address or port, set the `HOST` and `PORT` environment variables before starting the service.

Authentication is also enabled by default when running locally. To disable it when needed, such as during development, explicitly set the `AUTH_ENABLED=false` environment variable.

## Check the deployment

Visit the [health check endpoint](http://localhost:8000/healthz) to confirm that the API process responds to requests.
