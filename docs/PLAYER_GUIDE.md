# Player guide

[Project home](../README.md) · [Developer guide](DEVELOPING.md)

## Can I download and install it now?

**Not yet. There is no public player release or ready-to-use installer.** The
[Releases page](https://github.com/danielbuva/ror2-android-port/releases) is the
place to check for published releases, but there is currently no player download
there. Downloading this repository gives you development source, not an Android
game you can install.

The current builds are part of a developer testing setup. The build and install
commands in the developer guide depend on that setup and are not player
installation instructions. A release date is not established here.

## What is this project?

The aim is to run Risk of Rain 2 directly on Android. The tools adapt the original
PC game's code and convert its content for the Android version. Gameplay runs on
the Android device; a PC is not streaming the game to it.

You need to own a legitimate PC copy of Risk of Rain 2 and supply your own game
files. The repository does not provide the game, a free copy, or a way around
ownership checks. Generated game content is for the owner's local use and must
not be shared as a ready-made game package.

## What will installation involve?

The selected direction is an **owner-built version**: public tools plus your own
legitimate game files produce your local Android build. The details of how
players will obtain, prepare and install that build are still being worked out.

A phone-only process is being investigated, with a desktop build path as a
fallback. Small test programs have proved parts of that research, but there is
no demonstrated complete phone-only game build. There is no launcher or finished
installation sequence to recommend yet.

Before a player guide can give reliable installation steps, the project still
needs to settle and verify:

- How you supply your game files and which game versions are supported.
- Whether preparation can happen entirely on a phone or needs a computer.
- Device compatibility, Android version and storage requirements.
- Installation, updates, saved-progress retention and recovery when setup fails.

For the engineering decisions behind this, see the
[distribution plan](ADR-002-public-alpha-distribution.md),
[phone-only build assessment](phone-owner-build.md) and
[public alpha checklist](public-alpha.md). These are development documents, not
instructions to install a released game.

## What works, and what should I expect?

Developer tests have reached the original offline menu, selected survivors and
played through several original stage transitions. Android-local profiles,
results and settings also run. Many of these tests use automatic input,
invincibility or other diagnostic assists; they do not establish a complete,
normal-difficulty playthrough.

Important work remains:

- In-game audio is unavailable.
- A full unassisted run, the Moon finale and escape are not verified.
- Touch controls, physical controllers and ordinary player navigation still need
  qualification; automated test input does not prove those experiences work.
- Complete survivor abilities, expansion content and visual parity are unfinished.
- Sustained performance, heat and long-session stability remain open.
- Steam identity and cloud saves are unavailable in the current game setup.

Test-device results are not a supported-device list or a performance guarantee.
The [current technical status](../PORTING_STATE.md) is the source for detailed
results; [subsystem coverage](subsystem-coverage.md) explains individual systems.

## How can I follow or help?

Follow the [repository](https://github.com/danielbuva/ror2-android-port) and its
[Releases page](https://github.com/danielbuva/ror2-android-port/releases) for public
updates. Read the [technical status](../PORTING_STATE.md) for development progress.

If you want to contribute to the tools or documentation, start with
[getting involved](DEVELOPING.md#getting-involved). Do not upload game files,
generated game packages, account information or raw private logs when discussing
the project.
