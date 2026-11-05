# Contributing to Prism

Thanks for your interest. Prism is in its **design phase**, so the most useful contributions right now are:

- reviewing [docs/architecture.md](docs/architecture.md) and [docs/privacy.md](docs/privacy.md)
- weighing in on the open questions
- describing your use case, such as the platform you would connect or the reports you need

## How to contribute

1. **Discuss first.** For anything non-trivial, open an issue before writing a pull request.
2. **Design changes go through ADRs.** To propose a significant decision, add a file to `docs/adr/` with status `proposed` (see [ADR 0001](docs/adr/0001-record-architecture-decisions.md)).
3. **Keep pull requests focused.** One change per pull request, with a clear description of what changed and why.
4. **Sign off your commits** to certify the [Developer Certificate of Origin](https://developercertificate.org/):

   ```
   git commit -s -m "Describe your change"
   ```

## Ground rules

- Changes must not weaken the [privacy model](docs/privacy.md). Any change that touches data handling must say how it upholds those commitments.
- Be kind and constructive. All participation is covered by the [Code of Conduct](CODE_OF_CONDUCT.md).
- Report security or privacy vulnerabilities privately, as described in [SECURITY.md](SECURITY.md), not in public issues.

## License

By contributing, you agree that your contributions are licensed under the [Apache License 2.0](LICENSE).
