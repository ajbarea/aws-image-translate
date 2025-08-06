# Lenslate: AI-Powered Image Translator

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Lenslate is a cloud-native web application on AWS that lets users upload images to translate embedded text or browse a pre-loaded catalog automatically populated from Reddit's [r/translator](https://www.reddit.com/r/translator/) community and the [MMID](https://multilingual-images.org/) dataset. Once an image is selected, either manually or from our gallery, Lenslate initiates a high-speed serverless pipeline to extract text, detect its language, and generate translations. Behind the scenes, scalable AWS Lambda functions handle all image processing in a fully serverless architecture with automated deployment scripts and CI/CD testing pipelines.

## Core Workflow

- **Reddit & MMID Content Processing**: Automated scraping of images from MMID dataset and r/translator using Reddit API via EventBridge-triggered Lambda (every 5 minutes)
- **Amazon Rekognition**: AI-powered text detection and extraction from images (OCR)
- **Amazon Comprehend**: Auto-detects the source language of extracted text
- **AWS Translate**: Converts the extracted text into the user's chosen target language
- **DynamoDB State Management**: Tracks processed translations for user Translation History and Reddit duplicate prevention
- **S3 Storage**: Secure storage for downloaded images and processed content

All infrastructure is defined and managed with Terraform using a **two-stack approach for safe team collaboration**. The data-stack contains persistent resources that should never be destroyed (translation history, state management), while the app-stack contains resources that can be safely destroyed and recreated for development. The application features a responsive frontend hosted on S3 with CloudFront distribution, secured with Amazon Cognito for authentication. The backend uses AWS Lambda functions triggered via API Gateway for serverless image processing at scale, plus EventBridge-scheduled Reddit scraping for real-time gallery updates.

## ⚡ Quick Start

### One-Command Deployment

```bash
# 1. Clone the repository
git clone <repository-url> && cd lenslate

# 2. Set up environment (optional credentials can be left blank)
cp .env.example .env.local
# Edit .env.local only if you want Reddit gallery population or Google OAuth

# 3. Deploy infrastructure - fully automated!
python deploy.py
```

That's it! The automated deployment script handles everything:

- ✅ Validates prerequisites (Terraform, AWS CLI)
- ✅ Auto-installs missing tools with platform detection
- ✅ Builds all Lambda functions automatically
- ✅ Deploys both data-stack and app-stack infrastructure in the correct order
- ✅ Automatically configures cross-stack dependencies
- ✅ Provides error handling and auto-fixes
- ✅ Includes rollback capabilities on deployment failures
- ✅ Unique resource naming - no conflicts between teammates
- ✅ Automatic state management with S3 backend

### CI/CD Pipeline

Automated testing and build validation via AWS CodePipeline with buildspec.yml:

- **Completely Optional**: Only created if GitHub connection ARN is provided
- **Automated Testing**: Runs the test suite on commits
- **Lambda Building**: Builds all Lambda functions in isolated environment
- **Build Validation**: Validates that all Lambda functions can be built successfully
- **Multi-Branch Support**: Separate pipelines for different environments
- **Manual Deployment Required**: AWS Pipeline prepares artifacts but does not deploy infrastructure as to not overwrite optional Google OAuth and Reddit gallery features

## Automated Deployment Features

Our `deploy.py` script provides fully automated deployment:

- **Prerequisites Validation**: Checks and auto-installs Terraform, AWS CLI, Python with platform detection (Windows/macOS/Linux)
- **Configuration Management**: Automatically generates terraform.tfvars from .env.local with validation
- **Lambda Build System**: Compiles all Lambda functions with dependency management and packaging
- **Two-Stack Deployment**: Safely deploys data-stack (persistent) and app-stack (ephemeral) infrastructure in the correct order
- **Cross-Stack Dependencies**: Automatically configures app-stack to reference data-stack resources
- **Error Recovery**: Intelligent error analysis with suggested fixes and automatic rollback capabilities
- **State Management**: Automatic backup and migration of Terraform state with team collaboration support
- **Cross-Platform**: Native support for Windows, macOS, and Linux environments
- **CI/CD Integration**: Compatible with AWS CodeBuild for automated testing and build validation

## Infrastructure as Code (IaC)

### Two-Stack Architecture for Safe Team Collaboration

**Data Stack** (`terraform/data-stack/`):

- **Persistent shared infrastructure** - never destroyed
- S3 backend for Terraform state management
- DynamoDB for state locking
- Core shared resources (translation tables, history tables)
- **Safe from `terraform destroy`** - only deployed once per team

**App Stack** (`terraform/app-stack/`):

- **Ephemeral application resources** - safe to destroy and recreate
- Cognito user pools, Lambda functions, API Gateway
- CloudFront distribution, S3 buckets
- EventBridge rules, Reddit processing infrastructure
- **Can be `terraform destroy`ed** for testing and development
- **Automatically references data-stack** - cross-stack dependencies handled by deploy script

This separation ensures that critical data (user translations, history) is preserved in the data-stack while allowing developers to freely experiment with app-stack resources. The data-stack acts as a foundation that persists across multiple app-stack deployments. The automated deployment script handles the complex cross-stack dependency configuration automatically.

### AWS Resources Provisioned

- **Cognito**: User authentication and identity pools
- **S3**: Image storage bucket and frontend hosting bucket
- **Lambda**: Serverless image processing functions
- **DynamoDB**: User translation history and session management
- **API Gateway**: RESTful endpoints for frontend-backend communication
- **CloudFront**: Content delivery network for global frontend distribution
- **EventBridge**: Scheduled Reddit scraping (every 5 minutes)
- **IAM**: Roles and policies for secure service-to-service communication

## Architecture Overview

### System Components

```text
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │   API Gateway    │    │   Lambda        │
│   (S3/CF)       │◄──►│   (REST API)     │◄──►│   Functions     │
│                 │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Cognito       │    │   S3 Storage     │    │   DynamoDB      │
│   (Auth)        │    │   (Images)       │    │   (State)       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                       ▲
                                ▼                       │
                       ┌──────────────────┐             │
                       │   AWS AI/ML      │─────────────┘
                       │   Services       │
                       │   (Rekognition,  │
                       │   Comprehend,    │
                       │   Translate)     │
                       └──────────────────┘
```

### Data Flow

1. **User Interaction**: Users access the frontend via CloudFront/S3, authenticate with Cognito
2. **Image Upload**: Images uploaded to S3 trigger processing workflows
3. **API Communication**: Frontend communicates with Lambda via API Gateway
4. **AI Processing**: Lambda functions use Rekognition for text extraction, Comprehend for language detection, Translate for conversion
5. **State Management**: DynamoDB tracks processing state for Reddit pipeline and user sessions

### Reddit Pipeline with EventBridge

```text
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   EventBridge   │    │   Lambda         │    │   Reddit API    │
│   (5min timer)  │───►│   Scraper        │◄──►│   (PRAW)        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                       │
                                ▼                       ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │   DynamoDB       │    │   S3 Storage    │
                       │   (State Track)  │    │   (Images)      │
                       └──────────────────┘    └─────────────────┘
```

## Project Structure

```text
lenslate/
├── deploy.py               # Automated deployment orchestrator
├── buildspec.yml           # CI/CD testing and build configuration
├── package.json            # Frontend JavaScript dependencies and test scripts
├── jest.config.js          # Jest testing configuration
├── pyproject.toml          # Python project configuration
├── LICENSE.md              # MIT license
├── README.md               # Project documentation
├── deployment_logic/       # Deployment automation modules
│   ├── __init__.py
│   ├── deployment_orchestrator.py # Main deployment logic
│   ├── feature_handler.py  # Optional feature configuration
│   ├── progress_indicator.py # Console output formatting
│   ├── python_detector.py  # Python environment detection
│   └── resource_naming.py  # Unique resource name generation
├── lambda_functions/       # AWS Lambda functions
│   ├── __init__.py
│   ├── build_all.py        # Lambda build system
│   ├── build_lambda.py     # Individual Lambda builder
│   ├── image_processor.py  # Main image processing and translation
│   ├── reddit_populator_sync.py # Bulk Reddit scraping for initial population
│   ├── reddit_realtime_scraper.py # Real-time Reddit post processing via EventBridge
│   ├── reddit_scraper_sync.py # Core Reddit API integration with PRAW
│   ├── mmid_populator.py   # MMID dataset image sampling
│   ├── gallery_lister.py   # Gallery listing functionality
│   ├── cognito_triggers.py # Authentication triggers
│   ├── user_manager.py     # User management functions
│   ├── history_handler.py  # Translation history management
│   ├── aws_clients.py      # AWS service clients with circuit breakers
│   ├── prepare_reddit_populator.py # Reddit Lambda preparation script
│   ├── requirements.txt    # Lambda dependencies
│   └── build/             # Build artifacts directory
│       └── reddit_populator/ # Built Reddit Lambda package
├── tests/                  # Test suite
│   ├── __init__.py
│   ├── setup.js           # JavaScript test setup
│   ├── test-utils.js      # JavaScript test utilities
│   ├── auth.test.js       # Authentication unit tests
│   ├── auth-integration.test.js # Authentication integration tests
│   ├── auth-performance.test.js # Authentication performance tests
│   ├── test_buildspec.py  # CI/CD testing pipeline tests
│   ├── test_deploy.py     # Deployment automation tests
│   ├── test_deployment_orchestrator.py # Deployment orchestrator tests
│   ├── test_feature_handler.py # Feature handler tests
│   ├── test_history_handler.py # History handler unit tests
│   ├── test_mmid_populator.py # MMID populator unit tests
│   ├── test_progress_indicator.py # Progress indicator tests
│   ├── test_python_detector.py # Python detector tests
│   └── test_resource_naming.py # Resource naming tests
├── frontend/               # Web application
│   ├── favicon.ico        # Website favicon
│   ├── index.html         # Main application page
│   ├── css/
│   │   └── styles.css     # Modern responsive styling
│   ├── js/                # JavaScript modules
│   │   ├── app.js         # Main application orchestrator
│   │   ├── auth.js        # Authentication management
│   │   ├── component-loader.js # Dynamic HTML component loader
│   │   ├── config.js      # AWS configuration (generated by Terraform)
│   │   ├── config.js.template # Configuration template
│   │   ├── components/    # JavaScript component classes
│   │   │   ├── AuthComponent.js # Authentication UI
│   │   │   ├── BaseComponent.js # Base component class
│   │   │   ├── DashboardComponent.js # User dashboard
│   │   │   ├── FileUploadComponent.js # File upload handling
│   │   │   ├── FlipModalComponent.js # Image translation modal
│   │   │   ├── GalleryComponent.js # Image gallery
│   │   │   ├── LanguageSelectionComponent.js # Language picker
│   │   │   ├── ProfileComponent.js # User profile management
│   │   │   ├── ResultsComponent.js # Translation results display
│   │   │   └── UploadQueueComponent.js # Upload queue management
│   │   └── constants/
│   │       └── languages.js # AWS Translate language definitions
│   ├── components/        # HTML component templates
│   │   ├── confirmation-form.html # Email confirmation form
│   │   ├── dashboard.html # User dashboard layout
│   │   ├── file-upload.html # File upload interface
│   │   ├── gallery.html   # Image gallery layout
│   │   ├── header.html    # Page header
│   │   ├── language-selection.html # Language selection dropdown
│   │   ├── login-form.html # Login form
│   │   ├── profile.html   # User profile interface
│   │   ├── register-form.html # Registration form
│   │   └── upload-list.html # Upload queue display
│   └── resources/         # Static assets
│       ├── google-logo.svg # Google OAuth logo
│       ├── lenslate-logo.png # Application logo
│       └── images/        # Image assets directory
├── terraform/              # Infrastructure as Code (Two-Stack Architecture)
│   ├── reddit_populator.zip # Pre-built Lambda package
│   ├── data-stack/        # Persistent infrastructure - never destroyed
│   │   ├── main.tf        # Provider configuration and random ID
│   │   ├── backend.tf     # S3 backend and DynamoDB state lock
│   │   ├── dynamodb.tf    # Translation and history tables
│   │   ├── locals.tf      # Local variables and naming
│   │   ├── outputs.tf     # Shared resource outputs
│   │   └── variables.tf   # Input variables
│   └── app-stack/         # Ephemeral application resources - safe to destroy
│       ├── main.tf        # Provider and auto-generation configuration
│       ├── data.tf        # Data sources and remote state
│       ├── locals.tf      # Local variables and common tags
│       ├── variables.tf   # Input variables
│       ├── lambda.tf      # Lambda function definitions with EventBridge integration
│       ├── s3.tf          # S3 bucket configuration
│       ├── cognito.tf     # Authentication setup
│       ├── dynamodb.tf    # Reddit processing tables
│       ├── eventbridge.tf # Reddit scraping schedule (every 5 minutes)
│       ├── api.tf         # API Gateway configuration
│       ├── frontend.tf    # S3 hosting and CloudFront
│       ├── google-oauth.tf # Google OAuth configuration
│       ├── oauth-automation.tf # OAuth automation with Secrets Manager
│       ├── codepipeline.tf # CI/CD testing pipeline infrastructure
│       ├── outputs.tf     # Resource outputs
│       ├── config.js.tpl  # JavaScript config template
│       ├── env_to_tfvars.py # Environment variable to Terraform vars converter
│       ├── post_deploy_message.py # Post-deployment messaging
│       ├── sync_frontend.py # Frontend synchronization script
│       ├── update-google-oauth.py # Google OAuth update automation
│       └── user_reset.sh  # User management utilities
└── .env.example           # Environment variable template
```

## Team

- [**AJ**](https://github.com/ajbarea)
- [**Aditya**](https://github.com/adiplier)
- [**Ananth**](https://github.com/ananth-kamath-98)
- [**Andrew**](https://github.com/Andrewlee23)
- [**Chris**](https://github.com/C02022)

### Prerequisites

#### Required Software & Tools

- **[Terraform](https://www.terraform.io/downloads)** - Infrastructure as code deployment
- **[AWS CLI](https://aws.amazon.com/cli/)** - Configure with your AWS credentials  
- **[Python](https://www.python.org/downloads/)** - Backend services and Lambda functions
- **[Git](https://git-scm.com/downloads)** - Version control for cloning the repository

#### Required Accounts & Access

- **AWS Account** - **REQUIRED** for all AWS services
  - [Create AWS Account](https://aws.amazon.com/free/)
  - [AWS IAM Setup Guide](https://docs.aws.amazon.com/IAM/latest/UserGuide/getting-started.html)
  - **You must configure AWS CLI with `aws configure`** - This is the only mandatory credential requirement
  
- **Reddit Account & API Access** - **OPTIONAL** for automated gallery population
  - [Create Reddit Account](https://www.reddit.com/register/) (optional)
  - [Reddit App Registration](https://www.reddit.com/prefs/apps/) - Create a "personal use script" (optional)
  - [Reddit API Documentation](https://www.reddit.com/dev/api/) - API usage guidelines (optional)
  - **Note**: The app works perfectly without Reddit credentials - gallery features will simply be disabled

- **Google OAuth** - **COMPLETELY OPTIONAL** for "Sign in with Google" functionality
  - [Google Cloud Console](https://console.cloud.google.com/) (optional)
  - **Note**: If not provided, the Google sign-in button is automatically hidden

#### Setup Verification

Before proceeding, verify your setup:

```bash
# Check required tools
terraform --version
aws --version
python --version
git --version

# Verify AWS credentials
aws sts get-caller-identity
```

**Important**: The `aws sts get-caller-identity` command must work without errors. This is the only mandatory credential requirement for deployment.

### How to Deploy

#### Option 1: Automated Deployment (Recommended)

**Single command deployment with full automation:**

1. **Clone and setup environment**

   ```bash
   git clone <repository-url>
   cd lenslate
   ```

2. **Configure credentials (optional)**

   ```bash
   cp .env.example .env.local
   # Edit .env.local if you want Reddit gallery population or Google OAuth
   ```

3. **Deploy everything automatically**

   ```bash
   python deploy.py
   ```

**The automated deployment script:**

- ✅ Validates all prerequisites (Terraform, AWS CLI) with version checking
- ✅ Auto-installs missing tools on Windows/macOS/Linux
- ✅ Builds all Lambda functions with dependency management
- ✅ Generates terraform.tfvars automatically from .env.local
- ✅ Deploys data-stack (persistent infrastructure) and app-stack (ephemeral resources) in the correct order
- ✅ Automatically configures cross-stack dependencies
- ✅ Provides error analysis and auto-fixes
- ✅ Includes rollback capabilities on failures
- ✅ Cross-platform compatibility
- ✅ CI/CD integration with buildspec.yml for testing and build validation

#### Option 2: CI/CD Pipeline

**Automated testing and build validation via AWS CodePipeline:**

The repository includes a complete CI/CD pipeline configuration:

- **buildspec.yml**: Defines test and build validation steps
- **CodeBuild integration**: Automated testing and Lambda building
- **Multi-environment support**: Separate pipelines for different branches
- **Secrets management**: Uses AWS Secrets Manager for credentials

Commits to configured branches trigger automatic testing and build validation. **Manual deployment using `python deploy.py` is required** to deploy the infrastructure.

### Credential Configuration

**REQUIRED:**

- **AWS CLI**: Must be configured with `aws configure`

**OPTIONAL (for enhanced features):**

- **Reddit API credentials**: Get from <https://www.reddit.com/prefs/apps/> to enable gallery population from r/translator
- **Google OAuth credentials**: Get from <https://console.cloud.google.com/> to enable "Sign in with Google"

**What happens if you skip optional credentials:**

- **No Reddit credentials**: Gallery still works with MMID dataset images, Reddit features disabled
- **No Google OAuth**: Users can still authenticate with Cognito email/password, Google sign-in button hidden

#### Customizing Reddit Subreddits

By default, Lenslate monitors r/translator for images with translatable text. You can easily customize this to monitor multiple subreddits by editing your `.env.local` file:

```bash
# Reddit Subreddits Configuration
# Add subreddits as a comma-separated list (no spaces around commas)
REDDIT_SUBREDDITS=translator,language
```

**Examples:**

- `REDDIT_SUBREDDITS=translator` - Monitor only r/translator (default)
- `REDDIT_SUBREDDITS=translator,language` - Monitor r/translator and r/language
- `REDDIT_SUBREDDITS=translator,language,LearnJapanese` - Monitor multiple language-related subreddits

The configuration is centralized - changing this one line in `.env.local` updates:

- ✅ EventBridge scheduled scraping (every 5 minutes)
- ✅ Initial bulk population during deployment
- ✅ All Lambda functions that process Reddit content

#### 3. Access Your Application

Use the CloudFront URL provided in the Terraform outputs to access your live application!

#### 4. Development

For local development and testing:

```bash
# Sync frontend changes to S3/CloudFront
cd terraform/app-stack
python sync_frontend.py

# Update Google OAuth configuration after deployment
python update-google-oauth.py

# Frontend localhost at 8000
cd ../../frontend
python -m http.server 8000
```

**Note:** Google OAuth may not work when running locally on localhost

#### 5. Testing

The project includes tests for deployment automation, Lambda functions, and frontend components:

**Deployment Tests:**

```bash
# Install Python test dependencies
pip install -e ".[testing]"

# Test automated deployment system
pytest tests/test_deploy.py -v

# Test CI/CD buildspec testing configuration
pytest tests/test_buildspec.py -v
```

**Lambda Function Tests:**

```bash
# Run all Python Lambda tests
pytest tests/test_*.py

# Run tests with coverage
pytest tests/ --cov=lambda_functions --cov-report=html

# Run specific test file
pytest tests/test_history_handler.py
```

**Frontend JavaScript Tests:**

```bash
# Run all JavaScript tests
npm test

# Run specific test file
npm test auth.test.js

# Run tests with coverage
npm test -- --coverage

# Run tests in watch mode
npm test -- --watch
```

The test suite includes:

- **Deployment Tests**: Testing of `deploy.py` automation
  - Prerequisites validation testing
  - Terraform integration testing
  - CI/CD pipeline compatibility testing
  - Cross-platform deployment validation

- **Python Tests**: Mock-based testing of Lambda functions using `pytest`
  - Unit Tests: Individual Lambda function testing
  - Integration Tests: Using `moto` library to simulate AWS services
  - Edge Case Testing: Error condition coverage
  - DynamoDB Testing: Full simulation of database operations

- **JavaScript Tests**: Frontend component testing using `Jest`
  - Authentication module tests (`auth.test.js`)
  - UI component tests
  - Mock AWS SDK interactions
  - Browser environment simulation

#### 6. Clean Up

When you're done testing, easily destroy all AWS resources:

```bash
# Using automated script (recommended - handles both stacks safely)
python deploy.py --destroy

# Or manually (app-stack only - data-stack should be preserved)
cd terraform/app-stack
terraform destroy
```

**Important**: Only destroy the app-stack manually. The data-stack contains persistent resources (translation history, state management) that should be preserved across deployments.

This removes all AWS resources and stops charges. Your `.env.local` file remains for future deployments.

**Note**: The automated `--destroy` command safely handles both stacks in the correct order and includes user confirmation prompts for safety.

## 🔧 Troubleshooting

### Common Deployment Issues

#### "Python/Terraform/AWS CLI not found"

The `deploy.py` script automatically detects and installs missing prerequisites:

- **Windows**: Uses `winget` or `choco` for automatic installation
- **macOS**: Uses `brew` for automatic installation  
- **Linux**: Uses `apt` or `yum` for automatic installation

Or install manually:

- Python 3.8+: <https://python.org/downloads>
- Terraform 1.8+: <https://terraform.io/downloads>
- AWS CLI v2: <https://aws.amazon.com/cli/>

#### "AWS credentials not configured"

- Run `aws configure` and provide your AWS Access Key ID and Secret Access Key
- Test with `aws sts get-caller-identity`
- The `deploy.py` script validates credentials automatically

#### "Lambda build failed"

The deployment script provides intelligent error analysis:

- **Dependency issues**: Automatically retries pip installations
- **Permission errors**: Suggests running as administrator when needed
- **Network issues**: Provides connectivity troubleshooting steps

Run manually for debugging:

```bash
cd lambda_functions
python build_all.py --verbose
```

#### "Terraform deployment failed"

The deployment script includes automatic error recovery:

- **State lock issues**: Provides lock resolution commands
- **Resource conflicts**: Auto-generates unique resource names
- **Rollback capability**: Automatically reverts on critical failures

#### "Reddit features not working"

- This is expected if you didn't provide Reddit credentials
- The app still works with MMID dataset images
- Add Reddit credentials to `.env.local` and run `python deploy.py` again

#### "Google Sign-in button missing"

- This is expected if you didn't provide Google OAuth credentials  
- Users can still authenticate with email/password via Cognito
- Add Google OAuth credentials to `.env.local` and run `terraform apply` again if needed

### Known Issues

#### Python Executable Compatibility

The `deploy.py` script is currently hardcoded to use the `python` command and may not work in environments where you need to use `python3`:

- **Works with**: Systems where `python` points to Python 3.x (Windows, some Linux distributions, CI/CD environments)
- **May not work with**: Systems where only `python3` is available (some Linux/macOS configurations)
- **Workaround**: Create a symlink or alias from `python3` to `python`, or use a virtual environment where `python` is available
- **Background**: Cross-platform Python executable detection proved challenging across different shell environments, so we standardized on `python` for consistency with our CI/CD pipeline

This affects the automated deployment script but does not impact the deployed application functionality.

### Deployment Benefits

The Terraform deployment provides:

- **🔐 Secure Credential Management**: Store sensitive credentials in `.env.local` (gitignored)  
- **🔄 Automatic Configuration**: Terraform automatically generates `terraform.tfvars` from `.env.local`
- **🚀 Zero-Config Deployment**: Single `python deploy.py` command handles the entire deployment pipeline
- **🛡️ Graceful Degradation**: Missing optional credentials automatically disable related features instead of breaking
- **⚡ Rapid Iteration**: Quick redeployment for testing changes
- **🎯 Minimal Requirements**: Only AWS CLI configuration required - everything else is optional
- **🔗 Cross-Stack Dependencies**: Automatic handling of complex infrastructure dependencies

### Data Sources and Dependencies

- **Reddit API Integration**: Images are sourced from r/translator using Python Reddit API Wrapper (PRAW)
- **MMID Dataset Integration**: Automated sampling from the [Multilingual Multimodal Image Dataset (MMID)](https://multilingual-images.org/) - a public dataset containing images with text in multiple languages (Chinese, Hindi, Spanish, Arabic, French). The `lambda_functions/mmid_populator.py` function automatically downloads and populates your S3 bucket with diverse multilingual images for testing and demonstration.
- **AWS Services**: S3, Lambda, DynamoDB, Rekognition, Comprehend, Translate, Cognito, API Gateway, CloudFront, EventBridge
- **Backend Stack**: Python 3.11+ with boto3, asyncio for concurrent processing, PRAW for Reddit API
- **Frontend Stack**: Vanilla JavaScript with AWS SDK for browser, HTML5, and modern CSS with component-based architecture
- **Infrastructure**: All resources managed via Terraform with automated deployment system and two-stack architecture
- **CI/CD**: AWS CodePipeline with CodeBuild for automated testing and build validation

### Production-Ready Features

The application is fully functional with enterprise-grade infrastructure:

- ✅ **Automated Deployment**: One-command deployment with validation and error recovery
- ✅ **CI/CD Pipeline**: AWS CodePipeline with automated testing and deployment
- ✅ **Two-Stack Architecture**: Separation of persistent data infrastructure and ephemeral application resources
- ✅ **Reddit Streaming**: EventBridge-triggered real-time Reddit scraping from r/translator (every 5 minutes)
- ✅ **Backend Pipeline**: Automated image processing with AWS AI/ML services
- ✅ **Web Interface**: Complete frontend with authentication, file upload, and translation display
- ✅ **Team Collaboration**: Environment-specific resource naming with shared state management

### Key Features

#### Automated Deployment System

- **Prerequisites Validation**: Automatic detection and installation of Terraform, AWS CLI
- **Cross-Platform Support**: Windows, macOS, and Linux compatibility
- **Error Recovery**: Intelligent error analysis with suggested fixes and auto-rollback
- **Lambda Build System**: Automated compilation of all Lambda functions with dependency management
- **Configuration Auto-Fix**: Resolves common configuration issues automatically
- **CI/CD Integration**: Non-interactive mode for CodeBuild and other automation systems

#### Frontend Application

- **Authentication**: Secure user registration and login via AWS Cognito with optional Google OAuth
- **File Upload**: Drag-and-drop interface with progress tracking
- **Real-time Processing**: Live status updates during image processing
- **Multi-language Support**: Translation between 70+ languages
- **Results Display**: Side-by-side comparison of original and translated text
- **Gallery Browsing**: Pre-loaded images from Reddit and MMID dataset

#### Backend Pipeline

- **Asynchronous Processing**: Concurrent handling of multiple images using asyncio
- **State Management**: Persistent tracking via DynamoDB with environment-specific tables
- **Error Handling**: Error recovery and logging with circuit breakers
- **Scalable Architecture**: Serverless Lambda functions with automatic scaling
- **API Integration**: RESTful endpoints for frontend-backend communication
- **EventBridge Scheduling**: Automated Reddit scraping every 5 minutes

#### Content Integration

- **Reddit Streaming**: Real-time monitoring of r/translator with EventBridge triggers every 5 minutes
- **MMID Dataset**: Automatic sampling of multilingual images from the public MMID dataset
- **Image Filtering**: Smart detection of image posts with text content using AI/ML services
- **Duplicate Prevention**: Advanced content hashing and state tracking to avoid reprocessing images
- **Batch Processing**: Efficient handling of multiple posts per execution with concurrent processing
- **Real-time Updates**: Gallery auto-refreshes to show new Reddit images as they're processed

### How to Access and Use

#### Web Interface

1. **Access the application**: Navigate to the CloudFront URL provided in deployment outputs
2. **Authentication**: Create an account or log in using Cognito authentication (with optional Google OAuth)
3. **Upload or Browse images**: Choose between two experiences:
   - **Upload**: Use the drag-and-drop interface to upload your own images for translation
   - **Browse**: Explore pre-loaded images from Reddit's r/translator subreddit and the MMID multilingual dataset
4. **Interactive browsing**: For Reddit images, click on any image to flip it over and reveal the translation interface
5. **Select target language**: Choose from AWS supported languages (English, Spanish, French, German, etc.)
6. **Process images**: Click "Process" to extract and translate text from images
7. **View results**: See both original detected text and translated text side-by-side

#### Backend Processing (AWS Lambda)

1. **Automated processing**: The system uses AWS Lambda functions for:
   - **S3 triggers**: Automatically process images uploaded to S3
   - **API Gateway**: Handle web interface requests
   - **EventBridge triggers**: Scheduled Reddit scraping every 5 minutes from r/translator
   - **Real-time streaming**: Captures new images from r/translator as they are submitted

2. **Lambda deployment**: The image processing logic is deployed as AWS Lambda functions:
   - `lambda_functions/image_processor.py`: Main image processing and translation logic
   - `lambda_functions/reddit_populator_sync.py`: Reddit scraping with EventBridge integration
   - `lambda_functions/cognito_triggers.py`: Authentication and user management

### Development Workflow

To avoid merge conflicts, regularly update your feature branch with the latest changes from the remote repository. Follow this workflow to keep your branch up to date and minimize issues:

1. Fetch the latest from remote

   ```bash
   git fetch origin
   ```

2. Switch to and update develop

   ```bash
   git checkout develop
   git pull origin develop
   ```

3. Create your feature branch off the updated develop

   ```bash
   git checkout -b feature/your-branch
   ```

4. Push the new branch and set its upstream

   ```bash
   git push -u origin feature/your-branch
   ```

5. Work on your code: commit locally as you go.

6. Before you push or at the start of each dev session, sync your branch with develop

   ```bash
   git fetch origin
   git checkout feature/your-branch
   git merge origin/develop
   ```

7. Resolve any conflicts, run your tests, and THEN you can push

   ```bash
   git push origin feature/your-branch
   ```

Doing this will catch conflicts early in your own branch, keep your PRs clean, and save everyone a huge headache when it’s time to merge and approve PRs.

## License

MIT License

See LICENSE for details.
