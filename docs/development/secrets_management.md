# Secrets Management

## Environment Variables

Local development should use a `.env` file for secrets such as API tokens and email credentials. The repository should not commit credential values.

## GitHub Secrets

For GitHub Actions or other automation, secrets should be stored in GitHub Secrets or equivalent secret storage. The workflow should reference them through environment variables rather than embedding them in the repository.

## Local Development

- Keep a local `.env` file outside version control.
- Use `.env.example` as a template for the required names and shape of variables.
- Do not hard-code secrets into source files, tests, or examples.

## Production Deployment

Production deployments should use the platform's managed secret storage. Secrets should be injected at runtime rather than baked into the image or repository.

## Secret Rotation

Secrets should be rotated periodically, especially API keys and SMTP credentials. Rotated values should be updated in the deployment environment and local development environment promptly.

## Never Committing Credentials

The repository should remain safe to share publicly. Any file containing real tokens, passwords, or private keys should be removed from history and replaced with placeholders.

## API Key Policy

- store API keys in environment variables or secret managers
- avoid logging raw secrets
- use least-privilege credentials where possible
- document which variables are required for each collector or integration
