# Release Notes

All major changes in each released version of IOTileTest are listed here.

## 0.3.1

- Add support for specifying a second condition in an on block.  You can
  specify up to two named events or stream conditions with a combiner of either
  'and' or 'or'.

## 0.3.0

- Add support for generic when blocks that support clock gating on any stream
  condition
- Add support for copying a constant value, e.g. inside of on block.  The
  syntax is `copy number => output stream;`

## 0.2.2

- Add support for user only and combined streamer selectors based on new
  firmware support

## 0.2.1

- Add test coverage for negative config variables and arrays

## 0.2.0

- Add support for updated stream selectors that include combined selectors
  and selectors that include important system break information like reboots
  in user data streamers.

## 0.1.2

- Support negative numbers and arrays.

## 0.1.1

- Fix stream allocation when triggering on an input stream

## 0.1.0

- First alpha release for internal testing
- Supports compiling sensor graphs, basic optimzations on the underlying graph
  to fix the major inefficiencies added by the compiler and then exporting the
  sensor graph for running on a device or simulating on a computer