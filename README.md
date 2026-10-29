<!-- Generated from private documentation source. Do not edit directly. Source SHA256: 47201f272527635e4061a5fbbe6255d2eff1cc75ef7fb9104ef1e4ea57ba803b -->

# termcade website

Static Astro website for termcade.

Install the [komizo release](https://github.com/nicodes/komizo#install) matching `komizo.lock`, then run:

```sh
komizo dev                 # Foreground development server
komizo check               # Build, output assertions and capture checks
komizo run captures        # Verify checked-in terminal captures
komizo describe            # Inspect tools and commands
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
