<!-- Generated from private documentation source. Do not edit directly. Source SHA256: 33b8bdb25066b5ae0c8c4bd6628f72e4a6dc79f1b4ecc2b3df43337b1c1dbdec -->

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

```sh
curl -fsSL https://www.termca.de/install | sh
```

See [termcade](https://github.com/aviorstudio/termcade#readme) for setup and installation options.
