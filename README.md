<!-- Generated from private documentation source. Do not edit directly. Source SHA256: c8796295bcc36b9f48208d90eadd589afc04763aeadf89a42c7b3f97b52d6ea9 -->

# termcade website

Static Astro website for termcade.

Install [mise](https://mise.jdx.dev/) and run `mise install`, then run:

```sh
mise run dev                 # Development server
mise run check               # Build, output assertions and capture checks
komizo run captures        # Verify checked-in terminal captures
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
