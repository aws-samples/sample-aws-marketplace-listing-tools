# Contributing

Thank you for your interest in contributing to the AWS Marketplace Seller Readiness Tool.

## Reporting Issues

Please open a GitLab issue describing the bug or feature request.

## Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-change`)
3. Make your changes
4. Test locally using `./build.sh` and `./serve.sh`
5. Commit with a clear message
6. Open a merge request against `main`

## Development Setup

```bash
# Deploy backend to your AWS account
./build.sh

# Serve frontend locally
./serve.sh
# Open http://localhost:8080
```

## Code Structure

See [ARCHITECTURE.md](ARCHITECTURE.md) for a full walkthrough of how the code works.

## License

By contributing, you agree your contributions will be licensed under the Apache 2.0 License.
