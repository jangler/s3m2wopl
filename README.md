# s3m2wopl

A public domain Python script that generates WOPL instrument banks from AdLib
instruments in ScreamTracker 3 modules.

S3M files containing **any** sample instruments are not currently supported.

## Usage

```
usage: s3m2wopl.py [-h] [-m] src [dst]

Convert a S3M to a WOPL instrument set.

positional arguments:
  src            source .s3m file
  dst            destination .wopl file

optional arguments:
  -h, --help     show this help message and exit
  -m, --monitor  monitor filesystem for changes (requires watchdog)
```

## Instrument mapping

By default, all instruments are placed in the melodic bank in the same order as
they appear in the S3M. Including a number in square brackets in the
instrument name (ex. `flute [74]`) maps the instrument to the corresponding
one-indexed melodic program number, and including a number in angle brackets
(ex. `kick <36>`) maps the instrument to the corresponding zero-indexed
percussion key.

Percussion instruments are played at C-2.

## Further reading

- <https://github.com/Wohlstand/OPL3BankEditor/blob/master/Specifications/WOPL-and-OPLI-Specification.txt>
- <https://moddingwiki.shikadi.net/wiki/S3M_Format>
