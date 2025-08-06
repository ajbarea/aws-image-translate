# Lenslate Development

Most of these scripts are in the root directory or `terraform\app-stack`

## Prerequisites

- AWS CLI configured (`aws configure`)
- Python 3.8+
- Node.js/npm (auto-installed by deploy script)
- Terraform (auto-installed by deploy script)

## Environment Setup

```bash
# Copy environment template (optional - app works without it)
cp .env.example .env.local
# Edit .env.local only for Reddit gallery, CI/CD, or Google OAuth features
```

## Core Commands

```python
# install dependencies
pip install -e ".[testing]"
npm install

# automated deployment
python deploy.py

# automated teardown
python deploy.py --destroy

# automated lint and test
python lint.py

# automated frontend refresh (s3 sync and Cloudfront distribution invalitation)
cd terraform/app-stack
python sync_frontend.py

# automated reddit configuration guide
python manage_reddit_gallery.py

# automated deletion of AWS resources
python full_cleanup.py

# automated deletion of tracked resources (generated script)
cd your_deployment
python cleanup_resources.py

# automated deletion of the users in cognito
cd terraform/app-stack
./user_reset.sh

```

`your_deployment` directory contains a resource tracking system that monitors all AWS resources created during deployment. The `cleanup_resources.py` script is auto-generated during deployment and provides targeted cleanup of specific tracked resources (S3 buckets, DynamoDB tables, etc.) for the current deployment.

## Full stack linting commands

```bash
# Python linting and formatting
isort .
flake8 .
pytest

# JavaScript/CSS linting (using npm scripts)
npm install
npm run lint:fix    # or: npx eslint . --fix
npm run stylelint:fix    # or: npx stylelint "**/*.css" --fix
npm test
```

## Available npm scripts

```bash
npm test           # Run frontend JavaScript tests
npm run lint       # Check JavaScript linting
npm run lint:fix   # Fix JavaScript linting issues
npm run stylelint  # Check CSS linting  
npm run stylelint:fix  # Fix CSS linting issues
```
