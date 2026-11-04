![Risk of Rain 2 for Android — unofficial conversion tool](docs/assets/branding/ror2-android-banner.png)

# Risk of Rain 2 for Android

A work-in-progress project to bring Risk of Rain 2 to Android, using game files
from a PC copy you own.

The project converts the original game's code and content so they can run
locally on Android. The game runs on the device itself, rather than streaming
from a PC. This repository contains the tools and instructions for that work;
it does not include the game or replace the need to own it.

## Can I play it yet?

**There is no public download or ready-to-use installer yet.** Development builds
run on test devices, but this is not a finished port. The
[Releases page](https://github.com/danielbuva/ror2-android-port/releases) has no
public player release to install.

Start with the **[player guide](docs/PLAYER_GUIDE.md)** for availability, what
owning the PC game means, and what is still being worked out for installation.

## Where things stand

- Phone-only reconstruction has [host readiness](docs/accepted-build-reconstruction.md)
  for 693 of 705 final files (685 raw-exact); whole-game content reconstruction is
  nearly closed. Complete phone production remains unverified.
- A lighting tolerance class has been decided; accepting lighting differences
  still requires numerical and visual verification.
- The lab build plays on the Retroid Nova at about 120 FPS in menus and about
  50 FPS median in [assisted gameplay tests](docs/performance-game.md). A full,
  unassisted run and sustained performance acceptance remain open.
- [Alpha gates](docs/public-alpha.md) still include establishing a memory bound,
  fixing the LightningStake NaN failure, and accepting phone-only installation
  and in-place updates.

These are development results, not a promise that the game is ready to play.
The [technical status](PORTING_STATE.md) records the latest verified results and
remaining limits.

## Find your way

| I want to… | Start here |
| --- | --- |
| Find out about playing and installation | [Player guide](docs/PLAYER_GUIDE.md) |
| Follow progress and known limitations | [Current technical status](PORTING_STATE.md) |
| Understand how the conversion works | [Architecture](docs/ARCHITECTURE.md) |
| Set up the development tools or find commands | [Developer guide](docs/DEVELOPING.md) |
| Contribute | [Getting involved](docs/DEVELOPING.md#getting-involved) |
| Explore the work needed before a public alpha | [Public alpha checklist](docs/public-alpha.md) |

This repository contains authored tooling, transformations and reviewed summaries,
plus two promotional-art graphics described in the
[branding and source notes](docs/assets/branding/README.md). Game files and
generated runtime content stay private; the project does not bypass ownership,
authentication or DRM checks.
