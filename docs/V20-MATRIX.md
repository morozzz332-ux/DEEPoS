# Матрица приёмки V20

Сгенерировано `tools/v20_matrix.py`. Не редактировать вручную.

- Версия прошивки: `0.51-v20-test`
- Систем в реестре: **175** — объединение `rom-folders.txt` и реестра донора без папки `bios`
- С установленным маршрутом: **127**
- Только предложен маршрут (ядро из ES): **15**
- Без маршрута: **33**
- Не видны лаунчеру (`нет папки`): **40**, из них с играми: **4**
- Установленных портов: **0**

> Игры есть, но лаунчер их не увидит: `alg`, `astrocde`, `mame2003`, `wolf`.

## Как читать статусы

| Статус | Значение |
|---|---|
| PASS | проверено на V20, доказательство в `matrix-evidence.tsv` |
| FAIL | проверено, не работает; причина в колонке evidence |
| BLOCKED | нельзя проверить без конкретной зависимости |
| NOT_RUN | ещё не проверялось |
| NOT_APPLICABLE | для этого маршрута проверка не имеет смысла |

Маршрут `предложен` значит, что ядро известно из `es_systems.cfg`, но в `emulators.toml`/`systems.toml` строки нет: запуск ещё не проверялся.

## Реестр систем

| Система | Видна | Название | Маршрут | Ядро | Форматы | BIOS | Игр |
|---|---|---|---|---|---|---|---|
| `3do` | да | 3DO | opera | `opera` | .iso .bin .chd .cue | panafz1.bin<br>(required) | - |
| `a2600` | да | a2600 | stella, копия `atari2600` | `stella` | .a26 .bin .zip .7z | - | - |
| `advision` | **нет** | Adventure Vision | предложен (mess) | `mess` | .zip .bin .7z | - | - |
| `alg` | **нет** | American Laser Games | BLOCKED | - | .alg | - | 1 |
| `amiga` | да | Amiga | puae2021 | `puae2021` | .adf .hdf .ipf .lha .m3u .zip | kick34005.A500<br>(required) | - |
| `amigacd32` | да | Amiga CD32 | puae2021 | `puae2021` | .ccd .chd .cue .iso .lha .m3u .mds .nrg | - | - |
| `amstradcpc` | да | CPC | crocods | `crocods` | .cpc .dsk .zip .7z | - | - |
| `apple2` | **нет** | Apple II | BLOCKED | - | .apple2 .do .dsk .hdv .po .sh .zip | - | - |
| `arcade` | да | Arcade | fbneo | `fbneo` | .zip .7z .cue | - | - |
| `arduboy` | да | Arduboy | arduous | `arduous` | .hex | - | - |
| `astrocde` | **нет** | Astrocade | предложен (mess) | `mess` | .zip .bin .7z | - | 2 |
| `atari2600` | да | Atari 2600 | stella | `stella` | .a26 .bin .zip .7z | - | - |
| `atari5200` | да | Atari 5200 | a5200 | `a5200` | .a52 .zip .7z | - | - |
| `atari7800` | да | Atari 7800 | prosystem | `prosystem` | .a78 .zip .7z | - | - |
| `atari800` | да | Atari 800 | atari800 | `atari800` | .car .xex .atx .bin .atr .rom .zip .7z | - | 1 |
| `atarijaguar` | да | Atari Jaguar | virtualjaguar | `virtualjaguar` | .j64 .jag .rom .abs .cof .bin .prg | - | - |
| `atarilynx` | да | Atari Lynx | handy | `handy` | .lnx .zip .7z | - | 1 |
| `atarist` | да | Atari ST | hatari | `hatari` | .st .msa .stx .dim .ipf .m3u .zip | - | - |
| `atarixegs` | **нет** | Atari XEGS | предложен (atari800) | `atari800` | .car .xex .atx .bin .atr .rom .zip .7z | - | - |
| `atomiswave` | да | Atomiswave | flycast | `flycast` | .7z .ist .zip .bin | - | - |
| `bbcmicro` | да | BBC Micro | b2 | `b2` | .dsd .ssd | - | - |
| `bk` | да | bk | BLOCKED | - | - | - | - |
| `c128` | да | C128 | vice_x128 | `vice_x128` | .7z .bin .cmd .crt .d2m .d4m .d64 .d6z .d71 .d7z .d80 .d81 .d82 .d8z .g41 .g4z .g64 .g6z .gz .m3u .nbz .nib .p00 .prg .t64 .tap .tcrt .vfl .vsf .x64 .x6z .zip | - | - |
| `c16` | да | C16 | vice_xplus4 | `vice_xplus4` | .7z .bin .cmd .crt .d2m .d4m .d64 .d6z .d71 .d7z .d80 .d81 .d82 .d8z .g41 .g4z .g64 .g6z .gz .m3u .nbz .nib .p00 .prg .t64 .tap .tcrt .vfl .vsf .x64 .x6z .zip | - | - |
| `c64` | да | C64 | vice_x64 | `vice_x64` | .7z .bin .cmd .crt .d2m .d4m .d64 .d6z .d71 .d7z .d80 .d81 .d82 .d8z .g41 .g4z .g64 .g6z .gz .m3u .nbz .nib .p00 .prg .t64 .tap .tcrt .vfl .vsf .x64 .x6z .zip | kernal-901227-03.bin<br>(required) | - |
| `carts` | **нет** | PICO-8 | BLOCKED | - | .png .p8 | - | - |
| `cavestory` | **нет** | Cave Story | BLOCKED | - | .dll .exe .so | - | - |
| `cdi` | да | cdi | same_cdi | `same_cdi` | - | - | - |
| `channelf` | да | ChannelF | freechaf | `freechaf` | .bin .rom .chf .zip | - | - |
| `chip-8` | да | chip-8 | jaxe | `jaxe` | - | - | - |
| `cmds` | **нет** | Retroarch | BLOCKED | - | .sh | - | - |
| `coco3` | **нет** | Color Computer 3 | BLOCKED | - | .bin .cas .ccc .dsk .rom .wav .zip | - | - |
| `coleco` | **нет** | ColecoVision | BLOCKED | - | .rom .ri .mx1 .mx2 .col .dsk .cas .sg .sc .m3u .zip .7z | - | - |
| `colecovision` | да | colecovision | gearcoleco, копия `coleco` | `gearcoleco` | .rom .ri .mx1 .mx2 .col .dsk .cas .sg .sc .m3u .zip .7z | - | - |
| `cps1` | да | Capcom System I | fbneo | `fbneo` | .zip .7z .cue | - | 118 |
| `cps2` | да | Capcom System II | fbneo | `fbneo` | .zip .7z .cue | - | 141 |
| `cps3` | да | Capcom System III | fbneo | `fbneo` | .zip .7z .cue | - | 27 |
| `daphne` | да | Daphne | daphne | `daphne` | .daphne | - | - |
| `dc` | да | dc | flycast, копия `dreamcast` | `flycast` | .7z .gdi .cdi .cue .chd .m3u | - | - |
| `doom` | да | Doom | BLOCKED | - | .wad .sh .doom | - | - |
| `dos` | да | DOS | dosbox_pure | `dosbox_pure` | .exe .com .bat .conf .cue .iso .zip .m3u .dosz | - | - |
| `dragon32` | **нет** | Dragon 32/64 | BLOCKED | - | .bin .cas .ccc .dsk .rom .wav .zip | - | - |
| `dreamcast` | да | Dreamcast | flycast | `flycast` | .7z .gdi .cdi .cue .chd .m3u | dc_boot.bin<br>(hle)<br>dc_flash.bin<br>(optional) | 38 |
| `easyrpg` | да | EasyRPG | easyrpg | `easyrpg` | .easyrpg .zip | - | 4 |
| `enterprise` | **нет** | Enterprise 64/128 | предложен (ep128emu_core) | `ep128emu_core` | .128 .bas .com .dsk .dtf .img .tap .trn | - | - |
| `famicom` | да | Famicom | fceumm | `fceumm` | .nes .unif .unf .zip .7z | - | 4650 |
| `fbn` | да | fbn | fbneo | `fbneo` | - | - | - |
| `fds` | да | Famicom Disk System | fceumm | `fceumm` | .nes .unif .unf .fds .zip .7z | - | - |
| `gameandwatch` | да | Game and Watch | gw | `gw` | .mgw | - | - |
| `gamegear` | да | Game Gear | genesis_plus_gx | `genesis_plus_gx` | .bin .gg .zip .7z | - | 536 |
| `gametank` | **нет** | GameTank | BLOCKED | - | .7z .gtr .zip | - | - |
| `gb` | да | Game Boy | gambatte | `gambatte` | .gb .gbc .dmg .zip .7z | - | 4171 |
| `gba` | да | Game Boy Advance | mgba | `mgba` | .gb .gbc .gba .zip .7z | gba_bios.bin<br>(hle) | 2846 |
| `gbah` | да | gbah | mgba, копия `gb` | `mgba` | .gb .gbc .dmg .zip .7z | - | - |
| `gbav` | да | gbav | mgba, копия `gba` | `mgba` | .gb .gbc .gba .zip .7z | - | - |
| `gbc` | да | Game Boy Color | gambatte | `gambatte` | .gb .gbc .dmg .zip .7z | - | 2654 |
| `gbch` | да | gbch | gambatte, копия `gbc` | `gambatte` | .gb .gbc .dmg .zip .7z | - | - |
| `gbh` | да | gbh | gambatte, копия `gb` | `gambatte` | .gb .gbc .dmg .zip .7z | - | - |
| `genesis` | да | Genesis | genesis_plus_gx | `genesis_plus_gx` | .mdx .md .smd .gen .bin .cue .iso .sms .gg .sg .sgd .68k .chd .zip .7z | - | - |
| `genh` | да | genh | genesis_plus_gx, копия `genesis` | `genesis_plus_gx` | .mdx .md .smd .gen .bin .cue .iso .sms .gg .sg .sgd .68k .chd .zip .7z | - | - |
| `gg` | да | gg | genesis_plus_gx, копия `gamegear` | `genesis_plus_gx` | .bin .gg .zip .7z | - | - |
| `ggh` | да | ggh | gearsystem, копия `gamegear` | `gearsystem` | .bin .gg .zip .7z | - | - |
| `gp32` | да | gp32 | mame | `mame` | - | - | - |
| `gx4000` | **нет** | GX4000 | BLOCKED | - | .cpr .dsk .zip | - | - |
| `intellivision` | да | Intellivision | freeintv | `freeintv` | .bin .int .zip .7z | - | - |
| `ios` | да | ios | BLOCKED | - | - | - | - |
| `j2me` | да | J2ME | freej2me | `freej2me` | .jar | - | - |
| `kodi` | **нет** | Kodi | BLOCKED | - | .sh | - | - |
| `love2d` | **нет** | Love2d | BLOCKED | - | .love | - | - |
| `lowresnx` | **нет** | LowRes NX | предложен (lowresnx) | `lowresnx` | .nx | - | - |
| `lynx` | да | lynx | handy | `handy` | - | - | - |
| `macintosh` | да | macintosh | minivmac | `minivmac` | - | - | - |
| `mame` | да | MAME2010 | mame2003_plus | `mame2003_plus` | .zip .7z .chd | - | 5241 |
| `mame2003` | **нет** | MAME2003 | предложен (mame2003_plus) | `mame2003_plus` | .zip .7z | - | 1 |
| `mastersystem` | да | Master System | genesis_plus_gx | `genesis_plus_gx` | .mdx .md .smd .gen .bin .cue .iso .sms .gg .sg .sgd .68k .chd .zip .7z | - | - |
| `md` | да | md | genesis_plus_gx, копия `megadrive` | `genesis_plus_gx` | .mdx .md .smd .gen .bin .cue .iso .sms .gg .sg .sgd .68k .chd .zip .7z | - | - |
| `megacd` | да | megacd | genesis_plus_gx, копия `segacd` | `genesis_plus_gx` | .mdx .md .smd .gen .cue .iso .sms .gg .sg .68k .chd .zip .7z .m3u | bios_CD_U.bin<br>(required)<br>bios_CD_E.bin<br>(required)<br>bios_CD_J.bin<br>(required) | - |
| `megadrive` | да | Megadrive | genesis_plus_gx | `genesis_plus_gx` | .mdx .md .smd .gen .bin .cue .iso .sms .gg .sg .sgd .68k .chd .zip .7z | - | 2094 |
| `megadrive-japan` | да | megadrive-japan | genesis_plus_gx, копия `megadrive` | `genesis_plus_gx` | .mdx .md .smd .gen .bin .cue .iso .sms .gg .sg .sgd .68k .chd .zip .7z | - | - |
| `megadriveh` | да | megadriveh | genesis_plus_gx | `genesis_plus_gx` | - | - | - |
| `megaduck` | да | Mega Duck | sameduck | `sameduck` | .bin .zip .7z | - | - |
| `moonlight` | да | moonlight | BLOCKED | - | - | - | - |
| `moto` | да | moto | theodore | `theodore` | - | - | - |
| `mplayer` | да | mplayer | BLOCKED | - | - | - | - |
| `msumd` | **нет** | Megadrive MSU | предложен (genesis_plus_gx) | `genesis_plus_gx` | .md | - | - |
| `msx` | да | MSX | bluemsx | `bluemsx` | .cas .dsk .mx1 .mx2 .rom .zip .m3u .7z | - | - |
| `msx2` | да | MSX 2 | bluemsx | `bluemsx` | .cas .dsk .mx1 .mx2 .rom .zip .m3u .7z | - | - |
| `mv` | **нет** | Microvision | BLOCKED | - | .bin | - | - |
| `n64` | да | N64 | mupen64plus_next | `mupen64plus_next` | .7z .n64 .v64 .z64 .zip | - | 504 |
| `n64dd` | **нет** | N64DD | BLOCKED | - | .d64 .n64dd .ndd .n64 .z64 | - | - |
| `naomi` | да | Naomi | flycast | `flycast` | .7z .ist .zip .bin .dat | - | - |
| `nds` | да | NDS | melonds | `melonds` | .7z .nds .zip | bios7.bin<br>(required)<br>bios9.bin<br>(required)<br>firmware.bin<br>(required) | 52 |
| `ndsiware` | да | ndsiware | melondsds, копия `nds` | `melondsds` | .7z .nds .zip | - | - |
| `neocd` | да | neocd | neocd, копия `neogeocd` | `neocd` | .cue .chd .m3u | - | - |
| `neogeo` | да | Neo Geo | fbneo | `fbneo` | .7z .cue .neo .zip | neogeo.zip<br>(required) | 1432 |
| `neogeocd` | **нет** | Neo Geo CD | BLOCKED | - | .cue .chd .m3u | - | - |
| `nes` | да | NES | fceumm | `fceumm` | .nes .zip .7z | - | 7263 |
| `nesh` | да | nesh | nestopia, копия `nes` | `nestopia` | .nes .zip .7z | - | - |
| `ngp` | да | Neo Geo Pocket | beetle_ngp | `beetle_ngp` | .ngp .ngc .zip .7z | - | - |
| `ngpc` | да | Neo Geo Pocket Color | beetle_ngp | `beetle_ngp` | .ngp .ngc .zip .7z | - | - |
| `odyssey2` | да | Odyssey2 | o2em | `o2em` | .bin | - | - |
| `onscripter` | **нет** | ONScripter | BLOCKED | - | .dat .txt | - | - |
| `openbor` | да | OpenBOR | BLOCKED | - | .pak | - | - |
| `palm` | да | Palm | mu | `mu` | .img .prc | - | - |
| `pc` | да | pc | dosbox_pure | `dosbox_pure` | - | - | - |
| `pc-8800` | да | pc-8800 | quasi88 | `quasi88` | - | - | - |
| `pc-9800` | да | pc-9800 | np2kai, копия `pc98` | `np2kai` | .cmd .d88 .fdi .hdi .zip | - | - |
| `pc98` | **нет** | PC98 | BLOCKED | - | .cmd .d88 .fdi .hdi .zip | - | - |
| `pce` | да | pce | beetle_pce_fast, копия `pcengine` | `beetle_pce_fast` | .pce .bin .zip .7z | - | - |
| `pcengine` | да | PC Engine | beetle_pce_fast | `beetle_pce_fast` | .pce .bin .zip .7z | - | 677 |
| `pcenginecd` | да | PC Engine CD | beetle_pce_fast | `beetle_pce_fast` | .pce .ccd .iso .img .chd .cue .m3u | syscard3.pce<br>(required)<br>syscard2.pce<br>(optional) | - |
| `pcfx` | да | PC-FX | beetle_pcfx | `beetle_pcfx` | .chd .zip .cue .ccd .toc | - | - |
| `pet` | да | pet | vice_xpet | `vice_xpet` | - | - | - |
| `pico` | **нет** | Pico | BLOCKED | - | .mdx .md .smd .gen .bin .cue .iso .sms .gg .sg .sgd .68k .chd .zip .7z | - | - |
| `pico-8` | да | pico-8 | fake08 | `fake08` | - | - | 12 |
| `pico8` | да | pico8 | fake08, копия `pico` | `fake08` | .mdx .md .smd .gen .bin .cue .iso .sms .gg .sg .sgd .68k .chd .zip .7z | - | - |
| `piece` | **нет** | P/ECE | BLOCKED | - | .pex .pfi | - | - |
| `pokemini` | да | pokemini | pokemini, копия `pokemonmini` | `pokemini` | .7z .min .zip | - | - |
| `pokemonmini` | **нет** | Pokemon Mini | предложен (pokemini) | `pokemini` | .7z .min .zip | - | - |
| `ports` | да | Ports | run-port.sh | - | .sh | - | - |
| `ps1` | да | ps1 | pcsx_rearmed, копия `psx` | `pcsx_rearmed` | .cue .img .mdf .pbp .toc .cbn .m3u .ccd .chd .zip .7z .iso | - | - |
| `psp` | да | PlayStation Portable | ppsspp | `ppsspp` | .chd .cso .iso .pbp | - | 735 |
| `pspminis` | да | Playstation Portable Minis | ppsspp, копия `psp` | `ppsspp` | .chd .cso .iso .pbp | - | - |
| `psx` | да | PlayStation | pcsx_rearmed | `pcsx_rearmed` | .cue .img .mdf .pbp .toc .cbn .m3u .ccd .chd .zip .7z .iso | scph5501.bin<br>(hle)<br>scph5502.bin<br>(hle)<br>scph5500.bin<br>(hle) | 122 |
| `puzzlescript` | **нет** | PuzzleScript | предложен (puzzlescript) | `puzzlescript` | .pz .pzp | - | - |
| `satellaview` | да | Satellaview | snes9x, копия `snes` | `snes9x` | .smc .sfc .bs .zip .7z | - | - |
| `saturn` | да | Saturn | yabasanshiro | `yabasanshiro` | .img .cue .chd .iso .m3u | sega_101.bin<br>(required)<br>mpr-17933.bin<br>(required) | - |
| `scummvm` | да | SCUMM Virtual Machine | scummvm | `scummvm` | .scummvm | - | 4 |
| `scv` | да | Super Cassette Vision | emuscv | `emuscv` | .0 .bin .cart .rom .zip | - | - |
| `sega32x` | да | Sega 32X | picodrive | `picodrive` | .32x .smd .bin .chd .md .gen .cue .iso .sms .68k .zip .7z | - | - |
| `segacd` | да | Sega CD | genesis_plus_gx | `genesis_plus_gx` | .mdx .md .smd .gen .cue .iso .sms .gg .sg .68k .chd .zip .7z .m3u | bios_CD_U.bin<br>(required)<br>bios_CD_E.bin<br>(required)<br>bios_CD_J.bin<br>(required) | - |
| `sfc` | да | Super Famicom | snes9x, копия `snes` | `snes9x` | .sfc .smc .zip .7z | - | 1085 |
| `sg-1000` | да | SG-1000 | gearsystem | `gearsystem` | .mdx .md .smd .gen .bin .cue .iso .sms .gg .sg .sgd .68k .chd .zip .7z | - | - |
| `sgb` | **нет** | Super Game Boy | предложен (mgba) | `mgba` | .gb .gbc .dmg .zip .7z | - | - |
| `sms` | да | sms | genesis_plus_gx, копия `mastersystem` | `genesis_plus_gx` | .mdx .md .smd .gen .bin .cue .iso .sms .gg .sg .sgd .68k .chd .zip .7z | - | - |
| `snes` | да | Super NES | snes9x | `snes9x` | .smc .sfc .fig .zip .7z | - | 3040 |
| `snes-hacks` | **нет** | Super NES Hacks | BLOCKED | - | .smc .fig .bs .st .sfc .gd3 .gd7 .dx2 .bsx .swc .zip .7z | - | - |
| `snesh` | да | snesh | snes9x, копия `snes` | `snes9x` | .smc .sfc .fig .zip .7z | - | - |
| `snesmsu1` | да | Super NES CD | snes9x, копия `snes` | `snes9x` | .smc .sfc .zip .7z | - | - |
| `solarus` | **нет** | Solarus | BLOCKED | - | .solarus .zip | - | - |
| `st-v` | да | st-v | BLOCKED | - | - | - | - |
| `sufami` | да | SuFami Turbo | snes9x, копия `snes` | `snes9x` | .smc .zip .7z | - | - |
| `supergrafx` | да | Super Grafx | beetle_supergrafx | `beetle_supergrafx` | .pce .sgx .cue .ccd .chd .zip .7z | - | - |
| `supervision` | да | Supervision | potator | `potator` | .bin .zip .7z | - | - |
| `tg16` | да | tg16 | beetle_pce_fast, копия `turbografx` | `beetle_pce_fast` | .pce .chd .zip .7z | - | - |
| `tg16cd` | да | tg16cd | beetle_pce_fast, копия `turbografxcd` | `beetle_pce_fast` | .pce .ccd .iso .img .chd .zip .cue .m3u | syscard3.pce<br>(required)<br>syscard2.pce<br>(optional) | - |
| `thomson` | **нет** | Theodore Thomson | предложен (theodore) | `theodore` | .fd .k7 .m5 .m7 .rom .sap | - | - |
| `ti99` | **нет** | TI99 | BLOCKED | - | .ctg | - | - |
| `tic-80` | да | tic-80 | tic80, копия `tic80` | `tic80` | .tic | - | - |
| `tic80` | **нет** | Tic-80 | предложен (tic80) | `tic80` | .tic | - | - |
| `turbografx` | **нет** | Turbografx 16 | BLOCKED | - | .pce .chd .zip .7z | - | - |
| `turbografxcd` | **нет** | Turbografx CD | BLOCKED | - | .pce .ccd .iso .img .chd .zip .cue .m3u | - | - |
| `tvc` | **нет** | TV-Computer | предложен (ep128emu_core) | `ep128emu_core` | .cas | - | - |
| `uzebox` | да | Uzebox | uzem | `uzem` | .uze | - | - |
| `vb` | да | vb | beetle_vb, копия `virtualboy` | `beetle_vb` | .vb .vboy .zip .7z | - | - |
| `vectrex` | да | Vectrex | vecx | `vecx` | .vec .zip .7z | - | - |
| `vic20` | да | VIC-20 | vice_xvic | `vice_xvic` | .20 .40 .60 .7z .a0 .b0 .bin .cmd .crt .d2m .d4m .d64 .d6z .d71 .d7z .d80 .d81 .d82 .d8z .g41 .g4z .g64 .g6z .gz .m3u .nbz .nib .p00 .prg .rom .t64 .tap .tcrt .vfl .vsf .x64 .x6z .zip | - | - |
| `videopac` | да | Videopac G7000 | o2em | `o2em` | .bin .zip | - | - |
| `vircon32` | да | Vircon32 | vircon32 | `vircon32` | .v32 | - | - |
| `virtualboy` | да | Virtualboy | beetle_vb | `beetle_vb` | .vb .vboy .zip .7z | - | - |
| `vmac` | **нет** | Macintosh | предложен (minivmac) | `minivmac` | .cmd .dsk .hvf .img .zip | - | - |
| `vmu` | **нет** | Dreamcast VMU | предложен (vemulator) | `vemulator` | .vms .bin | - | - |
| `wasm4` | да | WASM-4 | wasm4 | `wasm4` | .wasm | - | - |
| `windows` | да | windows | BLOCKED | - | - | - | - |
| `wolf` | **нет** | Wolfenstein | BLOCKED | - | .wolf .ecwolf | - | 1 |
| `wonderswan` | да | WonderSwan | beetle_wswan | `beetle_wswan` | .ws .wsc .pc2 .zip .7z | - | - |
| `wonderswancolor` | да | WonderSwan Color | beetle_wswan | `beetle_wswan` | .ws .wsc .pc2 .zip .7z | - | - |
| `ws` | да | ws | beetle_wswan, копия `wonderswan` | `beetle_wswan` | .ws .wsc .pc2 .zip .7z | - | - |
| `wsw` | да | wsw | beetle_wswan, копия `wonderswancolor` | `beetle_wswan` | .ws .wsc .pc2 .zip .7z | - | - |
| `x1` | да | Sharp X1 | x1 | `x1` | .dx1 .zip .2d .2hd .tfd .d88 .88d .hdm .xdf .dup .cmd | - | - |
| `x68000` | да | Sharp x68000 | px68k | `px68k` | .dim .zip .2hd .d88 .88d .hdm .hdf .xdf .dup .cmd .m3u .img | iplrom.dat<br>(required)<br>cgrom.dat<br>(required) | - |
| `zmachine` | да | zmachine | mojozork | `mojozork` | - | - | - |
| `zx` | да | zx | fuse, копия `zxspectrum` | `fuse` | .sna .szx .z80 .tap .tzx .gz .udi .mgt .img .trd .scl .dsk .zip .7z | - | - |
| `zx81` | да | ZX81 | 81 | `81` | .p .tzx .zip | - | - |
| `zxspectrum` | да | ZX Spectrum | fuse | `fuse` | .sna .szx .z80 .tap .tzx .gz .udi .mgt .img .trd .scl .dsk .zip .7z | - | - |

## Проверки по маршрутам

Колонки совпадают с `matrix-evidence.tsv`; пустая ячейка — `NOT_RUN`.

| Система | Ядро | core_load | stand | menu | video | audio | controls | sticks | volume | fn_save | exit | sram | exit_state | resume | reboot | recovery | performance |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `3do` | `opera` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `a2600` | `stella` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `advision` | `mess` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `amiga` | `puae2021` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `amigacd32` | `puae2021` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `amstradcpc` | `crocods` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `arcade` | `fbneo` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `arduboy` | `arduous` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `astrocde` | `mess` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `atari2600` | `stella` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `atari5200` | `a5200` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `atari7800` | `prosystem` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `atari800` | `atari800` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `atarijaguar` | `virtualjaguar` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `atarilynx` | `handy` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `atarist` | `hatari` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `atarixegs` | `atari800` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `atomiswave` | `flycast` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `bbcmicro` | `b2` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `c128` | `vice_x128` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `c16` | `vice_xplus4` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `c64` | `vice_x64` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `cdi` | `same_cdi` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `channelf` | `freechaf` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `chip-8` | `jaxe` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `colecovision` | `gearcoleco` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `cps1` | `fbneo` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `cps2` | `fbneo` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `cps3` | `fbneo` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `daphne` | `daphne` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `dc` | `flycast` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `dos` | `dosbox_pure` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `dreamcast` | `flycast` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `easyrpg` | `easyrpg` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `enterprise` | `ep128emu_core` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `famicom` | `fceumm` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `fbn` | `fbneo` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `fds` | `fceumm` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `gameandwatch` | `gw` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `gamegear` | `genesis_plus_gx` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `gb` | `gambatte` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `gba` | `mgba` |  |  |  |  | PASS |  |  |  |  |  |  |  |  |  |  |  |
| `gbah` | `mgba` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `gbav` | `mgba` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `gbc` | `gambatte` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `gbch` | `gambatte` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `gbh` | `gambatte` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `genesis` | `genesis_plus_gx` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `genh` | `genesis_plus_gx` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `gg` | `genesis_plus_gx` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `ggh` | `gearsystem` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `gp32` | `mame` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `intellivision` | `freeintv` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `j2me` | `freej2me` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `lowresnx` | `lowresnx` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `lynx` | `handy` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `macintosh` | `minivmac` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `mame` | `mame2003_plus` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `mame2003` | `mame2003_plus` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `mastersystem` | `genesis_plus_gx` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `md` | `genesis_plus_gx` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `megacd` | `genesis_plus_gx` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `megadrive` | `genesis_plus_gx` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `megadrive-japan` | `genesis_plus_gx` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `megadriveh` | `genesis_plus_gx` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `megaduck` | `sameduck` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `moto` | `theodore` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `msumd` | `genesis_plus_gx` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `msx` | `bluemsx` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `msx2` | `bluemsx` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `n64` | `mupen64plus_next` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `naomi` | `flycast` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `nds` | `melonds` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `ndsiware` | `melondsds` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `neocd` | `neocd` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `neogeo` | `fbneo` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `nes` | `fceumm` |  |  |  |  | PASS |  |  |  |  |  |  |  |  |  |  |  |
| `nesh` | `nestopia` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `ngp` | `beetle_ngp` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `ngpc` | `beetle_ngp` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `odyssey2` | `o2em` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `palm` | `mu` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `pc` | `dosbox_pure` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `pc-8800` | `quasi88` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `pc-9800` | `np2kai` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `pce` | `beetle_pce_fast` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `pcengine` | `beetle_pce_fast` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `pcenginecd` | `beetle_pce_fast` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `pcfx` | `beetle_pcfx` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `pet` | `vice_xpet` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `pico-8` | `fake08` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `pico8` | `fake08` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `pokemini` | `pokemini` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `pokemonmini` | `pokemini` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `ports` | - |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `ps1` | `pcsx_rearmed` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `psp` | `ppsspp` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `pspminis` | `ppsspp` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `psx` | `pcsx_rearmed` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `puzzlescript` | `puzzlescript` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `satellaview` | `snes9x` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `saturn` | `yabasanshiro` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `scummvm` | `scummvm` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `scv` | `emuscv` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `sega32x` | `picodrive` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `segacd` | `genesis_plus_gx` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `sfc` | `snes9x` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `sg-1000` | `gearsystem` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `sgb` | `mgba` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `sms` | `genesis_plus_gx` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `snes` | `snes9x` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `snesh` | `snes9x` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `snesmsu1` | `snes9x` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `sufami` | `snes9x` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `supergrafx` | `beetle_supergrafx` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `supervision` | `potator` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `tg16` | `beetle_pce_fast` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `tg16cd` | `beetle_pce_fast` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `thomson` | `theodore` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `tic-80` | `tic80` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `tic80` | `tic80` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `tvc` | `ep128emu_core` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `uzebox` | `uzem` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `vb` | `beetle_vb` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `vectrex` | `vecx` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `vic20` | `vice_xvic` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `videopac` | `o2em` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `vircon32` | `vircon32` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `virtualboy` | `beetle_vb` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `vmac` | `minivmac` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `vmu` | `vemulator` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `wasm4` | `wasm4` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `wonderswan` | `beetle_wswan` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `wonderswancolor` | `beetle_wswan` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `ws` | `beetle_wswan` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `wsw` | `beetle_wswan` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `x1` | `x1` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `x68000` | `px68k` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `zmachine` | `mojozork` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `zx` | `fuse` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `zx81` | `81` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `zxspectrum` | `fuse` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |

## Без маршрута

| Система | Видна | Тип | Что нужно |
|---|---|---|---|
| `alg` | нет | нет папки | папку в `rom-folders.txt` и отдельный рантайм |
| `apple2` | нет | нет папки | папку в `rom-folders.txt` и отдельный рантайм |
| `bk` | да | отдельный рантайм | команду запуска в `emulators.toml` |
| `carts` | нет | нет папки | папку в `rom-folders.txt` и отдельный рантайм |
| `cavestory` | нет | нет папки | папку в `rom-folders.txt` и отдельный рантайм |
| `cmds` | нет | нет папки | папку в `rom-folders.txt` и отдельный рантайм |
| `coco3` | нет | нет папки | папку в `rom-folders.txt` и отдельный рантайм |
| `coleco` | нет | нет папки | папку в `rom-folders.txt` и отдельный рантайм |
| `doom` | да | отдельный рантайм | команду запуска в `emulators.toml` |
| `dragon32` | нет | нет папки | папку в `rom-folders.txt` и отдельный рантайм |
| `gametank` | нет | нет папки | папку в `rom-folders.txt` и отдельный рантайм |
| `gx4000` | нет | нет папки | папку в `rom-folders.txt` и отдельный рантайм |
| `ios` | да | отдельный рантайм | команду запуска в `emulators.toml` |
| `kodi` | нет | нет папки | папку в `rom-folders.txt` и отдельный рантайм |
| `love2d` | нет | нет папки | папку в `rom-folders.txt` и отдельный рантайм |
| `moonlight` | да | отдельный рантайм | команду запуска в `emulators.toml` |
| `mplayer` | да | отдельный рантайм | команду запуска в `emulators.toml` |
| `mv` | нет | нет папки | папку в `rom-folders.txt` и отдельный рантайм |
| `n64dd` | нет | нет папки | папку в `rom-folders.txt` и отдельный рантайм |
| `neogeocd` | нет | нет папки | папку в `rom-folders.txt` и отдельный рантайм |
| `onscripter` | нет | нет папки | папку в `rom-folders.txt` и отдельный рантайм |
| `openbor` | да | отдельный рантайм | команду запуска в `emulators.toml` |
| `pc98` | нет | нет папки | папку в `rom-folders.txt` и отдельный рантайм |
| `pico` | нет | нет папки | папку в `rom-folders.txt` и отдельный рантайм |
| `piece` | нет | нет папки | папку в `rom-folders.txt` и отдельный рантайм |
| `snes-hacks` | нет | нет папки | папку в `rom-folders.txt` и отдельный рантайм |
| `solarus` | нет | нет папки | папку в `rom-folders.txt` и отдельный рантайм |
| `st-v` | да | отдельный рантайм | команду запуска в `emulators.toml` |
| `ti99` | нет | нет папки | папку в `rom-folders.txt` и отдельный рантайм |
| `turbografx` | нет | нет папки | папку в `rom-folders.txt` и отдельный рантайм |
| `turbografxcd` | нет | нет папки | папку в `rom-folders.txt` и отдельный рантайм |
| `windows` | да | отдельный рантайм | команду запуска в `emulators.toml` |
| `wolf` | нет | нет папки | папку в `rom-folders.txt` и отдельный рантайм |

## Порты

Порты не переданы (`--ports`).

