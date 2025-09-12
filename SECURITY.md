# Security Policy

## Supported Versions

The following versions of Notifier are currently supported with security updates:

| Version | Supported          | Environment       | Notes                     |
| ------- | ------------------ | ----------------- | ------------------------- |
| 3.0.x   | :white_check_mark: | GCP Production    | Current stable release    |
| 2.0.x   | :x:                | N/A               | Deprecated - Broken build |
| 1.0.x   | :white_check_mark: | Local Development | Local use only            |
| < 1.0   | :x:                | N/A               | Initial development       |

## Reporting a Vulnerability

We take the security of Notifier seriously. If you believe you've found a security vulnerability, please follow these steps:

### 🚨 How to Report
Create an issue on GitHub using the "Security Vulnerability" template. Please include:
- Detailed description of the vulnerability
- Steps to reproduce the issue
- Version affected
- Potential impact assessment

### 🔒 Security Practices
- **Secrets Management**: BOT_TOKEN and BOT_PASSWORD are stored as environment variables
- **Authentication**: Password protection prevents unauthorized bot access
- **Cloud Security**: Follows GCP security best practices
- **Dependencies**: Regular security updates of Python packages

### 🌐 Supported Environments
- **Production**: Google Cloud Run (v3.0+ only)
- **Development**: Local Python environment (v1.0+)
- **Unsupported/Not-Tested**: Heroku, AWS, Azure

Note: Version 2.0.x contains known deployment issues and conceptual errors. It should not be used in production, but may be useful for learning about Telegram bot development concepts.

For urgent security matters, please use the "URGENT" label when creating the issue to ensure prompt attention.
