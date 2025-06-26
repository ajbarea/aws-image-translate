# aws-image-translate

Prototyping an image translation system using AWS services.

## AWS Credentials Setup

Before running, make sure you have AWS credentials configured. Create the following files with your AWS access keys and region:

- `~/.aws/credentials`:

  ```ini
  [default]
  aws_access_key_id = YOUR_ACCESS_KEY_ID
  aws_secret_access_key = YOUR_SECRET_ACCESS_KEY
  ```

- `~/.aws/config`:

  ```ini
  [default]
  region=us-east-1
  ```

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate  # Windows
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Running the CLI

The main entry point is `main.py`, which provides a command-line interface to detect and translate text from images in an S3 bucket.

### Usage

```bash
python main.py [--bucket BUCKET] [--source-lang SRC_LANG] [--target-lang TGT_LANG]
```

- `--bucket`: S3 bucket name (default: value from `config.py`)
- `--source-lang`: Source language code (default: value from `config.py`)
- `--target-lang`: Target language code (default: value from `config.py`)

Example:

```bash
python main.py --bucket mybucket --source-lang es --target-lang en
```

If no arguments are provided, the defaults from `config.py` will be used.

## Environment Variables

Before running the application, create a `.env.local` file in the project root with your Reddit API credentials:

```env
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=python:translate-images-bot:1.0 (by u/yourusername)
```

Replace the values with your own Reddit API credentials. This file is required for the application to access Reddit APIs.

## Testing & Coverage

Run all tests with coverage:

```bash
pytest --cov=.
```

## References

- <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/rekognition.html#>
- <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/list_objects_v2.html>
- <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/translate/client/translate_text.html>
- <https://docs.aws.amazon.com/rekognition/latest/dg/text-detecting-text-procedure.html>
- <https://community.aws/content/2drbcpmaBORz25L3e74AM6EIcFj/build-your-own-translator-app-in-less-30-min>
