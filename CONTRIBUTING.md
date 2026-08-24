# Contributing

> Alpha software: ListKit is still in active design and
> development. The project direction, data format, and user experience may
> change quickly before beta or v1.0.

## Current Status

This repository is public so people can inspect, use, and fork the project, but
it is not currently accepting pull requests while the core product shape is
still being worked out.

Bug reports and focused feedback are welcome through GitHub Issues when the
project is ready for broader public testing. Please include:

- what you expected to happen
- what happened instead
- your macOS version
- your `listkit --version` output
- any relevant terminal output

## Release Guidance

For maintainers, the GitHub Release tag and the package version in
`pyproject.toml` must match so the in-app updater installs the expected version.

## Future Contribution Policy

Once the project reaches beta or v1.0, small and focused pull requests may be
considered. Good candidates include:

- clear bug fixes
- small documentation improvements
- narrow compatibility fixes
- small tests for existing behavior

Large feature additions, rewrites, broad roadmap changes, or new product
directions should start as a discussion first. Forking is encouraged for larger
experiments that do not fit the maintainer-directed roadmap.

Maintainer time is limited, so there is no guaranteed review or support
timeline.

## AI Assistance

Parts of this project, including code, documentation, and UX iteration, are
developed with assistance from AI coding tools.

AI assistance is part of the development workflow, but it does not replace human
review, testing, or maintenance. Accepted changes are reviewed, edited, tested,
and maintained by the project maintainer.

This project is still in an early maintainer-directed phase and is not currently
accepting pull requests. Once pull requests are in scope, contributors may use
AI tools, but should mention AI-assisted work in the pull request. AI-assisted
changes should be reviewed with the same care as any other code, and
contributors are expected to understand, test, and take responsibility for the
work they submit.
