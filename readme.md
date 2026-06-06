# Cube-Link

[![Security Scans](https://github.com/jackseceng/Cube-Link/actions/workflows/security.yml/badge.svg)](https://github.com/jackseceng/Cube-Link/actions/workflows/container.yml)
![Image Size](https://img.shields.io/docker/image-size/jackseceng/cube-link/latest)
![Codebase Size](https://img.shields.io/github/languages/code-size/jackseceng/Cube-Link)

This is the Python code, web assets and Docker configuration for a link shortening web app

- Try out the app at [cubel.ink](https://cubel.ink)

- Download the [DockerHub image](https://hub.docker.com/r/jackseceng/cube-link)

## Testing locally

Below are instructions for setting up the container locally on your machine for testing and development.

### Database

[Sign up for a free Turso account](https://app.turso.tech/signup), and create database with a table called `urls` in with the follwing SQL statement:
```SQL
CREATE TABLE
  urls (
    HASHSUM NUMERIC PRIMARY KEY NOT NULL,
    URL BLOB NOT NULL,
    SALT BLOB NOT NULL,
    CLICKS INTEGER NOT NULL DEFAULT 0,
    LASTCLICK TEXT NOT NULL DEFAULT 'YYYY-MM-DDTHH:MM:SS.ffffff'
  );
```
> [!TIP]
> To avoid cluttering up your database while testing locally, it is recommended you create 2 databases: One for testing and one for production

### Captcha & Web Assets Storage

First, [sign up for a free Cloudflare acccount](https://dash.cloudflare.com/sign-up)

Then, setup a turnstile widget for your TLD and localhost domains, guides are available in [the Cloudflare Turnstile docs](https://developers.cloudflare.com/turnstile/)

Next, setup R2 storage, and link your TLD to the service for production, guides are available in [the Cloudflare R2 docs](https://developers.cloudflare.com/r2/)

Once you have the storage set up, upload your static Javascript and image assets to the route of your bucket, making sure their names match what the HTML files reference in their headers.

You must also configure a CORS policy on each R2 bucket to allow the browser to load assets with SRI checks. In the Cloudflare dashboard, go to R2 > your bucket > Settings > CORS Policy and set the following, substituting the appropriate origin for each bucket:

For your dev bucket, use `http://localhost`:
```json
[
  {
    "AllowedOrigins": ["http://localhost"],
    "AllowedMethods": ["GET"],
    "AllowedHeaders": ["*"]
  }
]
```

For your production bucket, use your chosen TLD:
```json
[
  {
    "AllowedOrigins": ["https://<your-tld>"],
    "AllowedMethods": ["GET"],
    "AllowedHeaders": ["*"]
  }
]
```

> [!IMPORTANT]
> Without this CORS policy, the browser will block all static assets from loading, even if the request returns a 200 status code.

<!-- -->

> [!TIP]
> If you want to change the static web files files, either point your HTML to your locally hosted version, or upload your changed files to an R2 dev bucket manually running this AWS CLI docker container sync command from the root of the repository:
> ```txt
> docker run --rm -ti -v ~/.aws:/root/.aws -v ./app/static:/data amazon/aws-cli s3 sync /data s3://cubelink-web-assets --endpoint-url https://<your-r2-s3-endpoint>.eu.r2.cloudflarestorage.com
> ```
> Or, if you are outside the EU:
> ```txt
> docker run --rm -ti -v ~/.aws:/root/.aws -v ./app/static:/data amazon/aws-cli s3 sync /data s3://cubelink-web-assets --endpoint-url https://<your-r2-s3-endpoint>.r2.cloudflarestorage.com
> ```

### Local Environment

Create a file in the `/app` directory called `.env`, with the following contents, setting the appropriate values with your own substitutions

> [!TIP]
> If you made separate testing and production databases and R2 buckets, make sure to set the TOKEN, ENDPOINT and CDN values to their endpoints in your `.env` file

```txt
ENDPOINT="<your-turso-url>"
TOKEN="<your-turso-token>"
CF_SECRET="<your-cloudflare-secret-key>"
TLD=localhost
CDN="<your-dev-r2-url>"
```

> [!CAUTION]
> The `docker-compose.yaml` and `.env` files must reference the same variable names where applicable, also make sure the variable names are not set elsewhere in your testing environment.

### Launch Instance

From the root directory of this repository, run:
```bash
docker compose up -d --build
```
```bash
[+] Running (2/2)
 ✔ Network cube-link_ls-net   Created
 ✔ Container cube-link-app-1  Started
```

If succesful, app will be running at [http://localhost](http://localhost), it will connect to your Turso database over the internet.

You can re-run this command whenever you make changes to rebuild the container.

To shut down the service, run this command:
```bash
docker compose down
```

### Updating SRI Hashes

If you modify any static files in `app/static/`, you must regenerate the SRI hash for each changed file and update the corresponding `integrity` attribute in all HTML templates that reference it.

To generate a new hash for a file, run the following from the root of the repository:
```bash
openssl dgst -sha384 -binary app/static/<filename> | openssl base64 -A
```

For example, to regenerate the hash for `style.css`:
```bash
openssl dgst -sha384 -binary app/static/style.css | openssl base64 -A
```

Prefix the output with `sha384-` and replace the corresponding `integrity` attribute value in any HTML template under `app/templates/` that references that file.

To regenerate hashes for all static files at once:
```bash
for f in app/static/*; do echo "$(basename $f): sha384-$(openssl dgst -sha384 -binary $f | openssl base64 -A)"; done
```

> [!IMPORTANT]
> If you upload modified static files to your dev R2 bucket without updating the `integrity` attributes in the HTML templates, the browser will block those resources from loading.
> After updating the `integrity` attributes in the templates, you must rebuild the container with `docker compose up -d --build` for the changes to take effect.
> In production, you must also purge the Cloudflare cache for any updated files, otherwise the CDN will continue serving the old version.
> This can be done in the Cloudflare dashboard under Caching > Configuration > Custom Purge, entering the full URL of each updated file.

## AI Development

This project uses [Kiro](https://kiro.dev) as its AI-powered IDE — see [`.kiro/steering/project.md`](.kiro/steering/project.md) for the agent instructions and conventions that guide it.

## Developed by [Jack](https://jacksec.engineer)
