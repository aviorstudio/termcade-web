<!-- Generated from private documentation source. Do not edit directly. Source SHA256: 5eb82b578ab7ab49f149e1404d5129f5fda6ba14b910323c2d791d217b9ad0c1 -->

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
