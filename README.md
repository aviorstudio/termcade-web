<!-- Generated from private documentation source. Do not edit directly. Source SHA256: 662a7f6a1abcf17426506d49ee205bb14aae37aa6920a8197332ea6565e92079 -->

# termcade website

Static Astro website for termcade.

Install [mise](https://mise.jdx.dev/) and run `mise install`, then run:

```sh
mise run dev                 # Development server
mise run check               # Build, output assertions and capture checks
mise run captures        # Verify checked-in terminal captures
mise tasks ls            # Inspect tools and commands
```

Ctrl-C stops development. The capture checker verifies the pinned released CLI before executing it. This website needs no runtime credentials or credential `.env` file.

## Install the CLI

With curl:

```sh
curl -fsSL https://termca.de/install | sh
```

Or with mise:

```sh
mise use --global github:aviorstudio/termcade@latest
```

An icon-only copy control sits on the right inside each install-command outline and shows a checkmark after copying. If clipboard access is unavailable, the command remains selectable for manual copying.

See [termcade](https://github.com/aviorstudio/termcade#readme) for setup and installation options.

For contributor verification, prepare the pinned helper source before running native tasks:

```sh
git clone https://github.com/nicodes/tools.git .ci-tools
git -C .ci-tools checkout --detach 091101094fedf5ce2e67c339c1c9c842d6a662dc
mise install
mise run check
```

Build commands record source and exact regular output hashes. Declared tests produce evidence from the current verification session in `.artifacts/verification`.

`mise run dev` owns the checkout’s foreground process tree. Dependency preparation and the application use an isolated local environment through the pinned optional ghenv CLI; no account is needed. Startup refuses changes to the native task policy during preparation. `mise run stop` stops only that checkout, and `mise run clean` refuses cleanup while its session is active.

## Contributor task interface

Contributor tool versions and task entry points live in the native Mise configuration. Use `mise run lint` for source checks, `mise run test` for the applicable behavioral tests, and `mise run check` for the complete supported gate. `mise run clean` removes declared generated outputs while preserving source, credentials and retained data. Use `mise run dev` and `mise run stop` for this checkout's owned local session.
