# nxnative

Play your own Nintendo Switch and Switch 2 games natively on Apple silicon Macs, iPhone and iPad. One script packs your game into a Mac app or an unsigned IPA that you sideload.

It is not an emulator: the game's own code runs directly on the Apple chip, with Switch graphics rebuilt on Metal. Nothing from any game is in this repository, and the project is not affiliated with Nintendo or any game publisher.

[Games](#games) · [Community front ends](#community-front-ends) · [Requirements](#requirements) · [How to play](#how-to-play) · [Discussions](#discussions) · [For developers](#for-developers)

## This fork: swordboiMacNative

This is [nxnative](https://github.com/seedds/nxnative) with one game in mind, The Legend of Zelda: Ocarina of Time (Switch 2, `0400486024DEC000` v131072) as a Mac app, built and played on an Apple silicon Mac. What is here is source code. There is no app to download and nothing from the game is in this repository, as upstream: you build the app yourself, from your own dump.

**Building it.** The command is upstream's, with one variable in front of it:

```
DM_APP_GAME_MODE=1 python3 scripts/build_ipa_from_nsp.py <your .nup> --platform mac-app --work-dir <work> -o "Zelda Ocarina of Time.app"
```

With `DM_APP_GAME_MODE=1` the app asks macOS for Game Mode, and its launcher hands its own process to the game (`DM_LAUNCH_EXEC`) instead of starting the game as a child and waiting, so Game Mode applies to the game itself. This is the app we play: on our Mac Game Mode turns on with it. Without the variable the same command makes upstream's default, an app that does not ask for Game Mode. The build takes about an hour on an M5 and needs about 80 GB of free disk for its work folder and the app.

**What it carries.** It follows upstream `main` closely (this branch sits on upstream `b54968e7`, 9 Nov 2026) and has, on top of it:

- upstream pull requests that were still open when we needed them, applied with a three-way merge; each commit names the PRs it applies and their authors, whose work it is. Upstream has since merged its own versions of several of them, and the next update of this branch takes those instead. One of them, #2116, keeps an event the game signals from ending the command buffer, which this game does 21 times a frame; upstream merged its own version on 10 Nov;
- one commit of upstream `main` taken ahead of that update, `fd8188c9`: the submissions of a frame share a command allocator. This game makes 28-37 a frame from a pool of 8, and on our walk the submit thread waited for the GPU 2.5 times a frame; now it does not wait;
- memory at an area change: render targets the game has let go leave GPU memory with their sharing entry instead of 80 seconds later, and entries nothing looks up are swept every two seconds. The cause and the numbers are in the [game's note](dm/games/0400486024DEC000/README.md#memory);
- the game's starting settings: handheld, dynamic resolution on, native output and MetalFX for the game's upscaler, instead of docked at full resolution with the game's own. They are what the settings window shows until you change them; a choice you saved before stays yours;
- the Game Mode build above;
- a fixed render resolution (`DM_FIXED_RESOLUTION`, `DM_FIXED_SCALE`), a Metal HUD menu item (Window > Metal HUD), the Pro Controller's gyro zero learned at rest, and `DM_NVN_COND_CONSERVATIVE` as an A/B switch for the occlusion conditions.

**Where it stands** (10 Nov 2026, MacBook Pro M5, 24 GB): 60 fps in Hyrule Castle Town on the settings above, about 13 ms of GPU a frame at full screen. The stall at an area change that this page described until today is gone on this Mac. On our scripted walk the game's footprint peaks at 12.3 GB against 14.9 and the GPU's residency set at 8.0 GB against 11.5, and no 300-frame window is over 17.5 ms where ten of thirty-two were, seven of them at 42-69 ms. In the app at full screen with Game Mode on, one run each: no 300-frame window over 20 ms where the worst was 68, the submit thread never waiting for the GPU, the GPU's allocation at its peak 9.3 GB against 10.6. The footprint there is about what it was, 13.6 GB against 13.8: at full screen what is gone is the stall, not the memory. The Mac still reaches its floor of free pages for a moment when the area changes; other areas, interiors and long sessions are not measured yet.

**On a 16 GB Mac.** We do not have one, so what follows is an emulation: 8 GB of the 24 GB Mac held by wired memory that the system can neither compress nor page out ([`dm/tools/mem_ballast.c`](dm/tools/mem_ballast.c)), with the game and everything else living in the 16 GB left. There the same walk completes at 60 fps: footprint 11.4 GB, two 300-frame windows of 55 a little late (17.6 and 24 ms), none slow. Metal's working set and the memory the Mac reports still said 24 GB during it, so take it as a sign and not as a test. Two things to know if you play on 16 GB. Close what else is open: other apps' memory adds to the pressure. And leave the memory guard's margin at its default (`DM_NVN_SYS_MARGIN_MB`, 1,024 MB): with 2,048 MB the guard ended the game after three minutes of the same walk, while it was running at 60 fps. Tell us what you see in this fork's issues; the log has a line every 300 frames with the footprint.

**Evening of 10 Nov.** Five changes on top of the version above. Three fix pictures: Switch 2 uniform reads are no longer cut at the size the game binds (streaks from the horses and the slingshot, PR #2219), an indirect dispatch no longer shares an encoder with the work that writes its counts (holes in the flower bushes of Hyrule Castle's court, PR #2226), and a texture ID keeps its read mark when the game streams another texture into it (black frames on the castle town wall, upstream's 6d9edb07); they ran in a short walk with no slow frame. Two are about memory. A long session (28 minutes) crossed the point where the host stopped holding the render targets the dynamic resolution alternates between, and from there remade them every frame, at 10 fps with the memory climbing to 17 GB until a restart; the hold now shortens there instead of ending. And a **Memory** setting (Performance, `DM_MEMORY_GB`) tells the host how much of the Mac's memory to plan for, so its memory guard begins to let go sooner. Measured the next night on the M5 (the app at full screen with Game Mode, 150 s of our walk, one run each): with the hold's bound forced low, so the run starts past it, the host before these changes remade 40,331 textures and had two 300-frame windows over 17.5 ms, this one 21,135 and none; with Memory at 16 or 12 GB, none over 17.5 ms either (at 12 GB the guard let go of a few dozen textures at a time). The setting does not lower the footprint much in a run this short (12.2-12.4 GB). Not measured yet: a session as long as the one that found the problem. If you are on the version before this push and a long session falls to 10 fps after an area change, `DM_NVN_ALIAS_KEEP_MB=16000` avoids it.

**11 Nov.** Three changes from upstream, two of them already in upstream `main`:
- a CPU write to a host page that two pools share is no longer missed while a pool buffer is made (`1e69c180`; a tester no longer saw Goron City's ground strobe);
- the host builds at `-O2` (`c4ffb9df`);
- texture views are cached by the Metal texture they are made of (PR #2260 by roandegraaf: a Hyrule Field view at 52-53 → 56-57 fps on an M4 Pro).

Two diagnostics come with them, both off by default:
- `DM_NVN_TEX_BREAKDOWN` logs the render targets' Metal memory against the guest storage they stand for;
- `DM_NVN_RT_LOSSY` compresses render targets with loss: 0.7 GB less memory on our walk. Its picture has not been compared yet, so leave it off.

On our walk, on a quiet M5, this version runs as the one before: no 300-frame window over 17.5 ms, 13.1 ms of GPU a frame, 12.5 GB resident. Still open: the terrain sometimes shows the wrong surface until the game reloads it, which we are tracing, and memory that keeps growing in sessions of an hour or more (upstream PR #2344 has the cause, not in this version yet).

Bugs in what this fork adds go in this fork's issues; everything else belongs to [upstream](https://github.com/seedds/nxnative/issues). The game's note is [dm/games/0400486024DEC000/README.md](dm/games/0400486024DEC000/README.md).

## Games

The full [tested games table](dm/games/README.md#games) includes original Switch games, tested builds, engines and graphics APIs. Each game's note records its tested platforms, progress and known issues.

These Switch 2 games have passed Mac gameplay testing. Build them from a [`.nup` file or a dump folder](#switch-2-games):

- [Donkey Kong Bananza](dm/games/040074A01BF12000/README.md)
- [Fire Emblem Fortune's Weave](dm/games/04007EF01F8AE000/README.md) — up to 120 fps
- [Hyrule Warriors: Age of Imprisonment](dm/games/04003F40232DE000/README.md)
- [Kirby Air Riders](dm/games/040077201BE50000/README.md)
- [Mario Kart World](dm/games/0400C3F00006E000/README.md)
- [Mario Tennis Fever](dm/games/0400D4201C6EA000/README.md)
- [Pokémon Pokopia](dm/games/0400A3A01EE4C000/README.md)
- [Splatoon Raiders](dm/games/0400380020056000/README.md)
- [Star Fox](dm/games/0400E88025B1A000/README.md)
- [The Legend of Zelda: Ocarina of Time](dm/games/0400486024DEC000/README.md)
- [Yoshi and the Mysterious Book](dm/games/0400245021D2C000/README.md)

## Community front ends

Community projects build on nxnative with tools to turn your games into apps for your iPhone, iPad or Mac without the command line, and libraries to organize and launch them. They are separate projects: questions and bugs about them go to their own pages.

- [NX2Apple](https://github.com/LNPANDY/NX2Apple) — Mac builder with a shared iPhone/iPad game library.
- [NX Play](https://github.com/varyform/nx-native-wrapper) — Mac library with device installs and save sync.
- [NxNative Launcher](https://github.com/rennan101/nxnative_Launcher) — Mac launcher with guided builds and controller mapping.
- [LumaNX](https://github.com/Xc1Ym/LumaNX) — Mac game builder with IPA export.
- [GameCase](https://github.com/Tiaoge-tou/GameCase) — iOS game library based on LiveContainer.

## Requirements

- **Mac:** Apple silicon, macOS 26.6 or later. Building games requires Xcode 27.2.
- **iPhone:** A17 Pro chip or later, with iOS 26 or later.
- **iPad:** M1 chip or later, with iPadOS 26 or later.

The games' textures are BC-compressed, which older iPhones cannot read. Switch 2 builds are tested on the Mac; check each game's note for device-specific validation.

For a game without a profile, the script writes a survey and tries a provisional build with guessed settings. That build may not start; see [Port another game](docs/development.md#port-another-game).

## How to play

Switch 2 games are built from one `.nup` file or a folder of their files, not from NSPs, and are tested on the Mac only: see [Switch 2 games](#switch-2-games).

### Build from the command line

You need a Mac with macOS 26.6 or later, [Xcode](https://developer.apple.com/download/all/?q=Xcode%2027.2) 27.2, [Homebrew](https://brew.sh) and Python 3.12 or newer (an arm64 one, not an Intel Homebrew's). An iPhone build also needs Xcode's iOS platform (Xcode → Settings → Components).

The shaders are built with Xcode 27.2's Metal compiler. Select it before step 1: `sudo xcode-select -s /Applications/Xcode.app`. With several Xcode versions installed, name this one `Xcode-27.2.app` and select it with `sudo xcode-select -s /Applications/Xcode-27.2.app`.

**1. Install the tools** (only once), in Terminal:

```
xcodebuild -downloadComponent MetalToolchain
git clone https://github.com/seedds/nxnative.git && cd nxnative
brew install xcodegen zstd glslang
brew install --cask dotnet-sdk
python3 -m pip install lz4 "capstone>=5,<6" fonttools nsz zbic "backports.zstd; python_version < '3.14'"
```

**2. Put your game in a folder**: the game, plus its update and DLC if you have them (`.nsp`, `.xci`, `.nsz` or `.xcz`):

```
~/Games/MarioWonder/
  Super Mario Bros. Wonder [010015100B514000][v0].nsp
  Super Mario Bros. Wonder [010015100B514800][v327680].nsp
```

**3. Build**, with your game folder and your `prod.keys`:

```
python3 scripts/build_ipa_from_nsp.py ~/Games/MarioWonder -k ~/keys/prod.keys
```

The IPA appears in the game's folder. The first build takes 30–60 minutes and needs free disk space of about twice the game's size plus 10 GB; building again is much faster.

To play on the Mac instead, add `--platform mac-app`: you get a Mac app of the game to open from Finder. All options: [The packing script in detail](docs/development.md#the-packing-script-in-detail).

### Install

Install the IPA on your iPhone or iPad with a sideloading tool such as AltStore, Sideloadly or LiveContainer. If your tool offers **Increased Memory Limit**, turn it on: the bigger games need it.

Game too big to install? Build again with `--romfs separate`, and run the command the script prints once to copy the game files to your phone ([Quick reinstalls](docs/development.md#quick-reinstalls)). With AltServer, also add `--shader-files`: it cannot install a file of 2 GiB or more.

Controls, saves and settings: [Playing](docs/playing.md).

### Switch 2 games

A Switch 2 game is built from one [NUP](https://github.com/a55uka/nup) container (a `.nup` file) or a folder of its files, not from NSPs. Neither needs `prod.keys`. A game this project has no profile for is surveyed and gets a provisional profile, as NSPs do ([Port another game](docs/development.md#port-another-game)), which may not boot. You get a Mac app; iPhone and iPad are untested.

**From a `.nup` file**, which holds the base game, its updates and DLC in one file. Give the file, or a folder that holds it:

```
python3 scripts/build_ipa_from_nsp.py ~/Games/DonkeyKongBananza.nup --platform mac-app
```

[Hyrule Warriors: Age of Imprisonment](dm/games/04003F40232DE000/README.md) is played this way: its 47 GB NUP unpacks in under five minutes. A NUP that carries the game's control data (its NACP) and icon gives the app the game's name and icon; otherwise the name comes from the game's profile and the app has no icon unless you give it one with `--icon <image>` (`ICON` in Spyder; a JPEG or PNG of any size).

A NUP without the base game also works, when its base package is empty or it has none and its updates are marked `standalone_update`: the update is taken as the whole game, and the script says so. If the game then stops on missing files, that update holds only what changed: pack a NUP with the base game. The newest update is selected by default; `--package v<N>` selects another version in the container. Such a container has no `v0` (base game) to select.

**From a folder of files**. The script expects this layout (`updates` and `dlc` are optional):

```
~/Games/DonkeyKongBananza/
  base/exefs/                     main, main.npdm, sdk, rtld
  base/romfs/
  updates/458752/exefs/           the update's version, as a decimal number
  updates/458752/romfs/           the patched RomFS, not a patch
  dlc/040074a01bf13001/0/romfs/   the DLC's title ID
```

```
python3 scripts/build_ipa_from_nsp.py ~/Games/DonkeyKongBananza --platform mac-app
```

An update's folder alone will do (no `base/`), and so will `exefs/` and `romfs/` directly in the folder, as `nup extract` writes them, which count as `base/`. The app has no icon, because the folder holds none; `--icon <image>` (`ICON` in Spyder) gives it one. To turn such a folder into a NUP: `nup pack ~/Games/DonkeyKongBananza game.nup`.

## Discussions

Questions, how a game runs on your Mac or iPhone, and ideas go in [Discussions](https://github.com/seedds/nxnative/discussions); [Issues](https://github.com/seedds/nxnative/issues) are for bugs, with the log. Ocarina of Time's performance (frame rate, resolution, which Macs hold 60 fps) is followed in [Ocarina of Time: state on main](https://github.com/seedds/nxnative/discussions/1789).

## For developers

[How it works](docs/development.md) · [Game notes](dm/games/README.md#games) · [Bring-up and debugging](docs/agents/README.md) · [Front ends](docs/frontends.md) · [Contributing](CONTRIBUTING.md)

## Acknowledgements

This project is built on other people's work ([licenses](dm/third_party/README.md)):

- **[d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile)** (MIT) developed this native-execution approach, for Diablo II: Resurrected. nxnative started as a copy of its generic parts: the NSO rewriter, the host that stands in for Horizon, the NVN-on-Metal layer and the iOS app shell. Fixes go both ways.
- **Ryujinx** (MIT): its shader translator (`Ryujinx.Graphics.Shader`, `Ryujinx.Common` and `Spv.Generator` 1.3.2, in `dm/third_party/ryujinx` with a few fixes listed in [its README](dm/third_party/ryujinx/README.md)) turns the games' shaders into SPIR-V. Its emulation of the kernel and system services is also a reference when the host's behaviour is in doubt.
- **[Atmosphère](https://github.com/Atmosphere-NX/Atmosphere)**: its kernel, mesosphère, is the reference for Horizon's synchronization semantics (address arbiter, condition variables).
- **[LibHac](https://github.com/Thealexbarney/LibHac)**: reads NSPs and layers updates over the base game in `dm/tools/nx_extract`.
- **[SPIRV-Cross](https://github.com/KhronosGroup/SPIRV-Cross)**: SPIR-V to Metal Shading Language.
- **[glslang](https://github.com/KhronosGroup/glslang)** compiles the GLSL of OpenGL games to SPIR-V for it.
- **[MacNativeGames](https://github.com/ly05010419/MacNativeGames)** (MIT): the GPU widening of 8-bit indices and in-pass clears in `dm/gfx/nvn/nvn_mtl.m`, and the visibility-counter lowering in the shader translator.

## License

MIT ([LICENSE](LICENSE)). Third-party code keeps its own license ([dm/third_party](dm/third_party/README.md)).
