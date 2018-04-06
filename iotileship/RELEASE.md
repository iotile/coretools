# Release Notes

All major changes in each released version of IOTileShip are listed here.

## HEAD

- Refactor to allow for shared resources to be used across action steps
- Improve python 3 compatibility
- Add support for sending a TRUB script as a step.
- Add support for autodetecting which variables need to be passed and which
  are optional.

## 0.0.1

- First Release. First definitions of RecipeObjects, RecipeActionObjects, and
  RecipeManager.
- Console script iotile-ship. Params include uuid, config file input, range,
  preserve temp files
- PromptStep, WaitStep, PipeSnippetStep, VerifyDeviceStep, SyncCloudStep