# Release Notes

All major changes in each released version of iotile-sensorgraph are listed
here.

## 1.1.0

- removed 3.6 support due to asyncio API change in 3.7
- Python 3.9 support

## 1.0.11

- Python compatibility set to 3.6-3.8 because of py35 EOL

## 1.0.10

- Add checksum to SensorGraph's class if it exists

## 1.0.9

- Add ability to force checksum calculation regardless of hash settings
- Fix checksum function's config dump to be sorted properly

## 1.0.8

- Add feature to set sensorgraph's checksum as config variable
- Add "__eq__ " methods to records

## 1.0.7

- Unpin iotile-core to support compatibility with `iotile-core` 5

## 1.0.6

- Fix py3 byte / str concat errors

## 1.0.5

- Implement proper dependency major version limits.

## 1.0.4

- Fix latent bug in usage of IOTileReading that flipped the timestamp and stream
  names.

## 1.0.3

- More builtins/__future__ removal that was missed

## 1.0.2

- Remove past/future/monotonic, pylint cleanup

## 1.0.1

- Add support for directly passing an sgf string to the parser.  This helps
  when compiling a sensorgraph programmatically.
- Drop python2 support

## 0.8.1

- Fix bug in iotile-sgcompile that could not write output formats to stdout
  on python 3.

## 0.8.0

- Fix critical bug in update script generation that incorrectly handled nodes
  that only had a single input and specified a triggering condition that 
  depended on the value of that input.  The result was that the node would
  fire every time the input changed, rather than just when the new value
  matched the expected triggering condition.

- Fix bug in script output_format to clear configs before adding new config 
  variables.

- Move reference controller and reference device classes out of
  iotile-sensorgraph and into new iotile-emulate package.

- Add support to SlotIdentifier for checking if the slot identifier matches a 
  given tile.

- Update SensorLog, InMemoryStorageEngine and StreamWalker to include additional
  features needed for iotile-emulate to work properly.

- Add support for fill-stop mode to SensorLog.  There is no way to use this from
  within iotile-sgrun itself currently but it is necessary for iotile-emulate.

- Adjust constant stream walker allocation to align with how physical devices
  behave in order to better integrate into iotile-emulate.

- Add better support for linking DataStreamer objects to a SensorLog and 
  generating reports.

- Enhances sensor-graph simulation to properly handle important system inputs
  by inserting an autocopy rule.

## 0.7.2

- Add support for broadcast streamers that indicate to the receiving tile that
  it should broadcast the streamed data rather than packaging it up as a
  historical report or sending it only when a user is online and connected.

## 0.7.1

 - on_block and copy_statement edited to prevent nodes from being dependent 
   on root node and a non-root node.

## 0.7.0

- Add reference tile and device for testing the effects of update scripts.  The
  device is reference_1_0 and the controller tile is refcon_1.

## 0.6.4

- subtract_a_from_b Node now fixed to subtract_afromb

## 0.6.3

- Move SetDeviceTagRecord into iotile-core since it is used in iotile-build now.

## 0.6.2

- Fix dead_code_elimination to not get rid of trigger_streamer nodes.

## 0.6.1

- Fix regression in ascii and snippet output formats caused by changes in 0.6.0.

## 0.6.0

- Add support for directly creating binary device updating scripts from an sgf
  file. There is a new `-f script` output format supportd in `iotile-sgcompile`
- Add UpdateRecord objects for all major sensorgraph update actions so that
  iotile-updateinfo can decode and display nice data on sensorgraph updates.
- Add single function for compiling and optimizing a sensorgraph: compile_sgf.
  This is accessible at iotile.sg.compile_sgf.

## 0.5.1

- Add support for subtract statement.  This complete support for all currently
  supported embedded processing nodes.  You can current subtract a constant
  stream from any other stream.

## 0.5.0

- Add dead code elimination for nodes that produce no visible output.  This
  improvement is necessary for the introduction of additional user ticks since
  they will generate a lot of unnecessary nodes in case the user wants to use 
  them.
- Improve remove-copylatest optimization pass.  We can now optimize cases where
  the copy-latest is on a constant node with multiple other nodes writing to
  that constant node.
- Topologically sort nodes during compilation to avoid issues when node lists
  are programmed into an IOTile device.  (Issue #315)
- Add support for removing unnecessary constant values that may be present
  after optimization.
- Adds the ability to specify an app_tag/app_version in an SGF file and output
  the right programming commands as a snippet.

## 0.4.0

- Improve the optimization of counter nodes by better downgrading split counters
  from copy_all to copy_latest when it can be proven that readings will arrive
  one at a time. (Issue #317)
- Add ability to simulate sensorgraphs and create traces that can be compared
  to ensure that the behavior of a sensor graph doesn't change.  (Issue #318)
- Fix bug in remove_copylatest optimization pass that would produce incorrect
  results if a node with copy_all_a was connected to a node that had been
  removed.  (Issue #320)
- Adds support for defining external stimuli into the sensor graph simulator
  either via command line or programmatically.  (Issue #321)

## 0.3.3

- Add support for parsing binary node descriptors.  (Issue #311)
- Fix incorrect pluralization of buffered streams

## 0.3.2

- Add support for two new ascii output formats: ascii and config that are 
  compatible with programmatically loading sensor graphs into iotile devices.
- Add support for passing hex encoded binary values in set config statements.
  The syntax is to pass hex:AABBCC with the hex encoded bytes following the hex:
  prefix.  This is decoded automatically into a bytes object.

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
