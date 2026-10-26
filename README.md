<!-- Generated from private documentation source. Do not edit directly. Source SHA256: 27f75a8e5a19df5bfd2c105578e58685a9b52d33b0f3ef5c7a8ce96f1e0809ec -->

# Termcade website

Static Astro website for Termcade.

Install the [Komizo release](https://github.com/nicodes/komizo#install) matching `komizo.lock`, then run:

```sh
komizo dev                 # Foreground development server
komizo check               # Build, output assertions and capture checks
komizo run captures        # Verify checked-in terminal captures
komizo describe            # Inspect tools and commands
```

Ctrl-C stops development. The capture checker verifies the pinned released CLI before executing it. This website needs no runtime credentials or credential `.env` file.
