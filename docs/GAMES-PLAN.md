# Что залить и что ставить: лучшие игры под R36S (RK3326)

Консоль: ArchR, PPSSPP (PSP), Flycast (Dreamcast), Genesis Plus GX / PicoDrive (Mega Drive), DuckStation (PS1).
Реальные ожидания: 2D — 60 fps, 3D — 25–40 fps с просадками. Ниже — только то, что реально играбельно.

## Sega: Mega Drive / Genesis (топ-10, идут на 60 fps)

Пак: `.bin/.gen/.md/.zip` → `/storage/roms/megadrive/`

| # | Игра | Почему |
|---|------|--------|
| 1 | Sonic 3 & Knuckles | эталон платформера, 60 fps |
| 2 | Sonic 2 | быстрее и злее, тоже 60 |
| 3 | Streets of Rage 2 | лучший beat'em up на консоли |
| 4 | Gunstar Heroes | самый плотный экшен на MD |
| 5 | Ristar | недооценённый платформер |
| 6 | Castlevania: Bloodlines | сложный, но отличный |
| 7 | Contra: Hard Corps | хардкорный run'n'gun |
| 8 | Phantasy Star IV | лучшая JRPG на MD |
| 9 | Shining Force II | тактическая RPG |
| 10 | Comix Zone | арт-дизайн и музыка |

Бонус, если есть: Landstalker, Beyond Oasis, Alien Soldier, Rocket Knight Adventures.

## Sega: Dreamcast (Flycast, 240p, топ-10 играбельных)

Пак: `.cdi/.gdi/.chd` → `/storage/roms/dreamcast/`; BIOS → `/storage/roms/bios/dc/` (`dc_boot.bin`, `dc_flash.bin`).

| # | Игра | Ожидаемый FPS |
|---|------|----------------|
| 1 | Marvel vs. Capcom 2 | 50–60 |
| 2 | Virtua Tennis 2 | 50 |
| 3 | ChuChu Rocket! | 60 (2D) |
| 4 | Power Stone 2 | 30–40 |
| 5 | Ikaruga | 30–40 |
| 6 | Crazy Taxi | 25–30 |
| 7 | Sonic Adventure | 25–30 |
| 8 | Soulcalibur | 25–30 |
| 9 | Dead or Alive 2 | 25–30 |
| 10 | Jet Set Radio | 20–25 |

Не грузить: Shenmue, Skies of Arcadia, Headhunter — 10–15 fps.

## PSP (PPSSPP, 1× разрешение, OpenGL, auto frameskip)

Пак: `.iso/.cso` → `/storage/roms/psp/`

| # | Игра | Ожидаемый FPS |
|---|------|----------------|
| 1 | Lumines | 60 |
| 2 | Patapon 2 | 30 (ритм — стабильно) |
| 3 | LocoRoco 2 | 30–60 |
| 4 | Disgaea: Afternoon of Darkness | 30+ |
| 5 | Final Fantasy Tactics: War of the Lions | 30 |
| 6 | Tactics Ogre: Let Us Cling Together | 25–30 |
| 7 | Metal Slug Anthology | 30–60 |
| 8 | Castlevania: The Dracula X Chronicles | 30 |
| 9 | Street Fighter Alpha 3 MAX | 60 |
| 10 | Tekken: Dark Resurrection | 30–40 |

Основной список — RPG/2D. God of War, Killzone, Monster Hunter — не тратить место.

## ПК-порты через PortMaster (ставятся сами, без ROM)

Уже стоит: Doom Engines, Wolfenstein 3D, Duke Nukem 3D (AWO), Quake 1, Quakespasm, Descent 1–2,
DevilutionX (Diablo 1), Aleph One Marathon 2, Abuse, Marathon 1, SRB2, SuperTux, Hurrican,
Cave Story, Celeste Classic, SDLPoP, OpenTyrian, 2048, Apotris, Annalynn, Canabalt, Cave Crawler, SPROUT.

Доставить позже (по желанию): `vcmi` (Heroes III), `openra`, `blood`, `hexen2`, `alephone-marathoninfinity`,
`duke3dawo`-аддоны, сборники OpenBOR.

## Как залить (одна дорога)

1. Подключить внешний диск с бэкапом (X:) и карту памяти — либо подключить консоль по USB и
   открыть в Проводнике `\\<console-ip>\games-roms` (логин `root`, пароль `archr`).
2. Копировать папками систем: `megadrive`, `dreamcast`, `psp`, `bios`.
3. Крупные копирования — `robocopy /Z /R:3` (с докачкой), не одним длинным потоком: NCM-канал
   иногда рвётся на файлах >100 МБ.
4. После копирования — перезапустить ES (`START → Quit`) или перезагрузить консоль, чтобы обновились списки.
