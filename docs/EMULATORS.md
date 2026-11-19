# Эмуляторы для DEEPoS на R36S-V20 (RK3326, 1 ГБ, 640×480)

Статус: исследование к 0.38, в образе эмуляторов пока нет. Документ отвечает на
вопрос «что ставить и в каком порядке», а не «как собрать прямо сейчас».

## Вывод

Для минимального rootfs выгодна схема «один RetroArch + несколько standalone»:

- 8/16-битные системы, GBA, Mega Drive/Genesis и PS1 закрываются libretro-ядрами;
- NDS, PSP, N64 и Dreamcast на A35 нормально живут только как standalone
  (libretro-варианты либо отсутствуют, либо заметно медленнее).

Развилка, которую нужно решить до сборки: **32-битный RetroArch** быстрее на
PS1/GBA/NDS-ядрах, но у него нет Vulkan; **64-битный** имеет Vulkan (плюс для
PSP/Dreamcast с PanVK, не плюс для PS1). Для первого релиза рекомендуется
64-битный RetroArch: один rootfs, проще сопровождение, Vulkan пригодится позже.

## Система → лучший вариант

| Система | Ядро/эмулятор | Зачем | Оговорки |
|---|---|---|---|
| NES/Famicom | `nestopia` | дефолт ArkOS, точный и быстрый; `quicknes` — фолбэк для минимума | часть хак-ромсетов лучше на `fceumm` |
| SNES | `snes9x` | полная скорость на 1.4 ГГц, лучший баланс | `snes9x2010` для хак-игр; bsnes/Mesen-S слишком тяжёлые |
| GB/GBC | `gambatte` | эталон точности, копеечная нагрузка | — |
| GBA | `mgba` | 99%+ совместимости, RTC | `gpSP` быстрее, но без GB/GBC и с глюками |
| NDS | **DraStic standalone** | единственный играбельный вариант на RK3326 | закрытый, **32-битный (armv7)** — нужен multiarch; проверять конкретную сборку |
| Mega Drive/Genesis | `genesis_plus_gx` | дефолт, полная скорость | `picodrive` — только для 32X и как «лёгкое» ядро |
| Master System/GG | `genesis_plus_gx` | та же семья чипов | PAL идут на ~17% медленнее NTSC |
| PS1 | `pcsx_rearmed` | 60 fps в нативе почти везде | 32-битная сборка быстрее; DuckStation — только для апскейла/PGXP |
| N64 | `mupen64plus_next` + GLide64mk2 | ~63% библиотеки | `parallel_n64` на RK3326 непригоден; Framebuffer Emulation OFF |
| PSP | **PPSSPP standalone 1.20.4+** | быстрее libretro-ядра; Vulkan даёт +10 fps на God of War | только курируемый список (~330 игр), 2× натив не тянет |
| Dreamcast/Naomi/Atomiswave | `flycast` | единственный вменяемый | DSP OFF, Alpha Sorting = Per-Strip; BIOS не обязателен (reios) |
| Аркады | **FBNeo** (база), `mame2003_plus` (фолбэк) | CPS1/CPS2/Neo Geo на полной скорости | romset жёстко привязан к версии ядра |
| PC Engine/TG-16 | `mednafen_pce_fast` | дефолт ArkOS, быстрый | CD-игры требуют `syscard3.pce` |
| Neo Geo | `FBNeo` | полная скорость MVS/AES | `neogeo.zip` нужен и в `/roms/bios`, и в папке ромов |
| Saturn | `yabasanshiro` (не в дефолт) | проходит compat-list standalone | по общему мнению на этом железе не стоит |

Источники: ArkOS wiki (архив), r36s.org (гайды по системам), списки совместимости
R36S, тема 4PDA 1083917 (посты p=146083594 про Arch R 3.1.0/PanVK, p=144062861
про 32-битное ядро PS1, p=140628265 про регресс DraStic).

## Что нужно в rootfs

| Слой | Состав | Оценка |
|---|---|---|
| GPU/дисплей | panfrost (`drm/panfrost`) + Mesa: `libEGL`, `libGLESv2`, `libgbm`, `libdrm`, DRI `panfrost_dri.so` | 5–8 МБ |
| RetroArch | сборка без Qt/X11/Wayland: KMS+EGL, ALSA, udev, только RGUI | 4–6 МБ |
| libretro-ядра | nestopia, gambatte, mgba, genesis_plus_gx, snes9x, mednafen_pce_fast, pcsx_rearmed | ~8 МБ после распаковки |
| Средние | flycast, mupen64plus_next, mame2003_plus | 20–40 МБ |
| Тяжёлые | PPSSPP standalone, FBNeo, DraStic | 40–80 МБ |
| Системные libs | `libstdc++`, `libgcc_s`, `zlib`, `libpng`, `freetype` + шрифт, `alsa-lib` + UCM, `libudev` | 6–10 МБ |
| BIOS | PS1 `scph5501.bin`, DC `dc_boot.bin`/`dc_flash.bin`, Sega CD, PCE CD, `neogeo.zip`, `awbios.zip` | data-раздел |

Размеры Mesa/ALSA — инженерные оценки, не замеры на этом железе; фактический
размер panfrost-стека надо мерить на собранном образе.

## Фазы

1. **P0 (ближайшая):** RetroArch + 7 лёгких ядер (NES/SNES/GB/GBA/MD/PCE/PS1) и
   `emulators.toml` для них. Проверить запуск ROM из launcher на железе.
2. **P1:** аркадный блок FBNeo и отдельный раздел под тяжёлые ядра, чтобы не
   раздувать rootfs.
3. **P2:** standalone PSP/N64/Dreamcast, затем NDS (DraStic, если решимся на
   multiarch).

## Ограничения и честные оговорки

- Прямых замеров «32-бит RA vs 64-бит RA» на PS1 в источниках нет — только
  заявления сообщества; решать по собственному замеру на железе.
- DraStic закрытый и 32-битный; ни в одном источнике не описано, как именно он
  сосуществует с aarch64-rootfs — нужен multiarch, это отдельная работа.
- Размеры ядер — zip-пакеты с libretro buildbot (aarch64), после распаковки
  ориентировочно ×2.
- FPS не обещаем до реальных замеров (K1/K3): цифры из отчётов сообщества —
  только ориентир для выбора ядра.
