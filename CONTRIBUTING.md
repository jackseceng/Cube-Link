# Contributing to the Cube-Link project

## Project Objectives

- A secure, Python Flask app that shortens URLs and re-directs users that go to the shortened URLs.
- Use modern development and deployment pipelines and technologies.
- Make use of automated DevSecOps tooling to detect vulnerabilities and bugs.
- Usage and/or contribution to this project must be done under the terms in the `LICENSE` file.

## Testing locally

Follow the instructions in the `readme` to test locally on your machine, please ensure that you can perform these steps before contributing to this project
- Any issues with testing locally should be raised as a bug on GitHub Issues
- Any fixes or workarounds for identified bugs should be raised on a relevant GitHub Issue

## Making PRs

When raising a pull request to this repository, there are several checks that must pass for code quality, security and standardisation reasons.

The checks will need to run their tools, and any findings must be resolved in order for your PR to be acceptable, they will run automatically when a Pull Request is raised.
> [!NOTE]
> Details about this process are on [the pipeline automation wiki page](https://github.com/jackseceng/Cube-Link/wiki/Pipeline-Automation#checking-pull-requests)

If all checks pass (or are justified as to why they don't to a `CODEOWNER`), The PR must be merged to the main branch for deployment of static assets and/or the container image.

## Support Expectations

The people listed in the `CODEOWNERS` file will aim to give to support when they can, but they are not obliged to.
- To raise a feature request or bug, please do so in GitHub Issues, using the templates provided. Aim to document as much detail as possible to assist with troubleshooting
- Any offensive or abusive language in tickets will result in a closure of the issue, and a ban from this repository for the offending user
- Any impatience will only waste yours and the code owners time, do not expect any rigid response times for issues raised.

Any community based support given must be in adherance to the rules written in the `CODE_OF_CONDUCT` file
- Breaches of this behaviour will not be tolerated, and will result in a ban from this repository for the offending user

Components of the software supply chain for this project will be patched if there is a remediation for an exploitable vulnerablility available.
- If this breaks fucntionality, this is unfortunate, but ultimately intended as per the primary objectives above.
