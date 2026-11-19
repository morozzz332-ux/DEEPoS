# DEEPoS · промт для нового агента: довести образ до загрузки на R36S-V20

> Передай этот файл целиком новому агенту. Он самодостаточен: внутри состояние, решения,
> команды, известные грабли и точный следующий шаг. Секретов и адресов здесь нет — только
> плейсхолдеры `<console-ip>`, `<pc-ip>`, `<repo>`.

## 0. Роль и цель

Ты — инженер-разработчик прошивки **DEEPoS** для портативной консоли **R36S-V20 (клон, плата
`R36S-V20 2025-05-18`)**. Проект уже собран, покрыт host-тестами и записан на microSD. Твоя
задача на этот заход: **добиться, чтобы образ загружался на реальной консоли**, и довести
первый буст до рабочего лаунчера (экран, кнопки, настройки, демо-порт). Всё остальное — код,
сборка, тесты, флешер — уже готово, ломать и переписывать не нужно без причины.

Правило работы: сначала диагностика по фактам (отчёт с карты, экран, UART/USB-консоль), потом
правка, потом host-тест, потом пересборка и только затем запись на карту.

## 1. Железо (проверено по плате и стоку)

| Узел | Что известно |
| --- | --- |
| SoC | Rockchip RK3326, 4× Cortex-A35, Mali-G31 MP2 |
| RAM | 1 ГБ LPDDR3 (одна микросхема; у ревизий Nanya `NT6CL256M32-H1` / XINYUEI `XT26S6M3Z0M-HI`), `MemTotal` ≈ 732 МБ |
| PMIC | RK817 (`rk817-battery`, `rk817-charger`, `rk817-codec`), топливомер кулоновский |
| Экран | ST7703, 640×480, DSI 4 lanes, 30 МГц, reset GPIO3_B7 (active low) |
| Кнопки | 19 GPIO-линий: gpio3 10–27 + gpio2 13/14, активный уровень низкий |
| Стики | ADC `adc-joystick` на каналах `saradc` |
| Звук | RK817 codec, динамик `spk-con-gpio` gpio3 pin 7 |
| USB | один OTG (данные) + отдельное гнездо CHARGE (питание) |
| Носитель | только microSD (eMMC нет) |
| Wi-Fi | нет |
| Батарея | 804068, 3500 мА·ч / 12.95 Вт·ч |

Пределы: CPU 408/816/1008/**1416** МГц (1512 недостижимо: нет `cpufreq/boost`, `vdd_arm` max
1.35 В), GPU 200/300/400/**650** МГц, троттлинг по 85 °C, RAM без пайки не расширить.

## 2. Что уже сделано (состояние на момент передачи)

Репозиторий: `<repo>\deepos` (remote `github.com/morozzz332-ux/DEEPoS`, ветка `main`,
HEAD `e670d10`). Локальные ветки/теги: `v0.1-docs`, `v0.1-prototype`.

Приложения (C11, статические aarch64, host-сборка тем же кодом):

- `apps/launcher` — UI на фреймбуфере: 6 вкладок (Продолжить / Игры / Настройки / Модули /
  Файлы / Сведения), 16-битный RGB565 через `/dev/fb0`, ввод evdev, настройки пишутся в
  `<data>/config/settings.toml` и применяются в sysfs, запуск игры по `emulators.toml`,
  `continue.tsv`, `--selftest` (отчёт о окружении), `--keys`, `--print-state`, `--fb`, `--apply`.
- `apps/modd` — супервизор модулей: UNIX-сокет, NDJSON JSON-RPC (совместим с Arch-R api 3),
  таймауты (initialize 10 с, action.invoke 1 с), watchdog 3 падения за 600 с.
- `apps/saved` — атомарное хранилище сейвов: слоты 0..4, `tmp → fsync → rename → fsync(dir)`,
  журнал и `recover` после сбоя.
- `apps/updatr` — A/B на устройстве: `boot.json` (slot/attempts/rollback/generation) плюс
  переписывание `root=PARTLABEL=…` в `extlinux.conf`, установка слота.
- `apps/playdemo` — крошечная игра для проверки экрана/кнопок (порт `demo.sh`).
- `modules/thermal`, `modules/saves` — модули с root-хелперами через файл-запрос.

Инструменты (`tools/`): `mkimage.py` (образ + GPT + загрузчики), `mkboot.py` (BOOT-дерево),
`build-rootfs.{sh,py}`, `build-kernel.sh`, `build-dtb.sh`, `build-uboot.sh`,
`import-loader.py` / `loader_donor.py` / `extract-loader.py` (донорская boot-цепочка),
`dpflash.py` (запись + `--resume/--verify/--expand/--list`), `expand_gpt.py`,
`verify-image.py`, `verify-card.py`, `preflight.py` (GO/NO-GO), `release.py`,
`read-report.py`, `gen-font.py`, `update.py`.

Тесты: **22 набора** (`tests/*_test.py`), запуск `sh tests/run-all.sh` внутри образа
`deepos-build:local`. Дополнительно `make preflight` (GO/NO-GO) и `make verify-image`
(проверка образа до записи).

Текущий образ: `build/deepos-r36s-v20.img`

- размер **4 294 967 296 B** (4 ГиБ), **sha256 `b5de8980dc9df69a180480cdbadc4ba37a96717a8e2cc0500539e0883b6e5cc5`**
- BOOT version **`0.26-dev`**
- `KERNEL` 74 490 368 B, sha256 `f91b62257a28c2369431e8e51c4058f7bffad6c7b267835dfac4b3829bd97729`
- `dtbs/rk3326-r36s-v20.dtb` 46 836 B, sha256 `430540c59e7d1b1255faf6c58b929c97a2b6ddd271dbf4ef2f8345ed70044688`
- rootfs squashfs ≈ 2.1 МБ, `logo.bmp`, `README-FIRST.txt`

Карта: microSD **уже записана** этим образом, SHA-256 содержимого сверен, обе GPT прочитаны
обратно. `GPT`, 5 разделов: `BOOT` 0.2 ГБ, `DEEPOS_A` 0.7, `DEEPOS_B` 0.7, `DATA` 1.5,
`ROMS` 0.9 ГБ. **Раздел ROMS не расширен** до полного объёма карты (см. §7).

**Загрузка на железе ещё не подтверждена**: отчёта с устройства нет, UART/COM-лог не снят.

## 3. Ключевые решения (почему сделано именно так)

1. **Загрузочная цепочка — донорская.** Своя сборка `idbloader`/`u-boot.itb` на этой плате не
   стартовала. Взята область 32 KiB…16 MiB из эталонного образа Arch-R clone (он на этой
   консоли загружается) байт-в-байт; наш GPT и разделы при этом остаются своими.
   Донорский U-Boot запускает `boot.scr`, поэтому при сборке пакетируется наш boot-скрипт
   (`board/r36s-v20/boot/boot.cmd`), который передаёт управление `extlinux`.
   Компоновка Arch-R не «FIT по 8 MiB»: там служебные блоки `LOADER` и FIT-образы по
   ~9.07 / 10.1 / 11.2 / 12.2 MiB — копировать надо регион целиком, не отдельный файл.
2. **Корень монтируется по PARTLABEL, а не по /dev.** `root=PARTLABEL=DEEPOS_A`
   (слот B — `DEEPOS_B`). Initramfs нет, `root=LABEL=` не разрешается, поэтому метки разделов
   (PARTLABEL в GPT) — единственный надёжный способ. `updatr` переписывает эту строку при
   переключении слота.
3. **Корневая ФС — squashfs только для чтения**, A/B через два слота (`DEEPOS_A`/`DEEPOS_B`),
   пользовательские данные отдельно на `DATA` (ext4, rw).
4. **BOOT начинается с 16 MiB** (`start_mib: 16` в `board/r36s-v20/layout.json`), чтобы не
   накрыть загрузочную область (32 KiB idbloader … 8 MiB U-Boot и служебные блоки).
5. **Нет композитора**: UI рисует в фреймбуфер напрямую (`CONFIG_DRM_FBDEV_EMULATION=y`),
   16 бит на пиксель, damage-based, ноль анимаций.
6. **Модули — отдельные процессы** с общей шиной JSON-RPC; привилегированные действия через
   файл-запрос и root-хелпер (модуль не имеет права писать в `/sys`).
7. **Запись карты: таблица пишется последней.** Сначала нулятся первые 34 сектора, пишется
   тело, в конце — GPT и резервная копия. Иначе Windows монтирует FAT и запись падает
   `win32=5`.
8. **Секреты не публикуются**: в репозитории только плейсхолдеры (`<console-ip>`, `<panel-token>`,
   `<host-key>`), pre-commit хук `tools/check-secrets.ps1` блокирует утечки.

## 4. Структура карты и загрузка

```
LBA 0        protective MBR
32 KiB       idbloader (донор)
8 MiB        U-Boot + служебные блоки (донор), boot.scr -> extlinux
16 MiB       BOOT (fat32): KERNEL, dtbs/, extlinux/, logo.bmp, MANIFEST.json, README-FIRST.txt
+256 MiB     DEEPOS_A (squashfs, root)
+700 MiB     DEEPOS_B (squashfs, слот B)
+700 MiB     DATA (ext4): config/, modules/, module-data/, saves/, boot.json
остаток      ROMS (exfat): md/, snes/, psx/, ports/, bios/, …
```

`extlinux/extlinux.conf` (внутри BOOT):

```
LABEL DEEPoS
LINUX /KERNEL
FDT /dtbs/rk3326-r36s-v20.dtb
APPEND root=PARTLABEL=DEEPOS_A rootfstype=squashfs ro rootwait rootdelay=3
       console=ttyS2,1500000n8 console=tty0 loglevel=7 vt.global_cursor_default=0
       nowatchdog mitigations=off zswap.enabled=1 psi=1 loop.max_loop=8 init=/sbin/init
```

`loglevel=7` и отсутствие `quiet` включены намеренно: при проблемах на экране должны идти
строки ядра, а не чёрный экран.

## 5. Что происходит при старте (rcS, по порядку)

`/etc/init.d/rcS` (busybox init):

1. mount `proc`, `sysfs`, `devtmpfs`, `devpts`, `tmpfs`, `mdev -s`;
2. `mount_part` BOOT → `/flash`, DATA → `/data`, ROMS → `/storage` (best-effort, без `set -e`);
3. `usb-gadget.sh` — configfs gadget: ACM (`ttyGS0`, getty 115200) + NCM (`usb0`, `<console-ip>`);
4. копирование `/usr/share/deepos/modules` → `/data/modules` и `/usr/share/deepos/roms` → `/storage`;
5. `launcher --apply --data /data` (применить `settings.toml` к sysfs);
6. `modd` (если есть `/data/modules`);
7. отчёт на BOOT: `/flash/report/{boot,mounts,free,dmesg,temps,cpufreq,modules,selftest}.txt`
   и `checks.txt` (`verdict=ok|FAIL`, `panel`, `data`, `input_events`, `mem_available_mb`, `soc_c`);
8. `selfcheck.sh` пишет вердикт; UI поднимается из `/etc/inittab` строкой
   `::respawn:/usr/bin/launcher` (упавший лаунчер перезапускается сам).

Доступы для диагностики: UART-гребёнка (3.3V/TX/RX/GND, `ttyS2`, 1500000, getty) и USB-консоль
(`ttyGS0`, 115200) — обе с логином `root` без пароля (порт физический, это осознанно).

## 6. Сборка и проверка (host, Linux-инструменты внутри Docker)

Работать в `<repo>\deepos`. На Windows `make` нет — либо запускать через `docker run`, либо
через Git-Bash/WSL. Основные команды (внутри образа):

```bash
make docker-image          # deepos-build:local — host-сборка и тесты
make docker-cross          # deepos-cross:local — кросс-компилятор aarch64
make kernel                # build/kernel/{Image,dtb,kernel.config,BUILD.txt}
make uboot                 # build/uboot/{idbloader.img,u-boot.itb} (вендорский форк)
make image-full LOADER_DONOR=../images/ArchR-clone.img.gz   # образ с донорской цепочкой
make preflight             # GO/NO-GO: артефакты загрузки
make verify-image          # GPT/CRC/сигнатуры ФС/загрузчики
sh tests/run-all.sh        # 22 набора host-тестов
```

Донорская цепочка подставляется в `mkimage.py` через `--loader-donor <образ>`; при этом
`--boot-script board/r36s-v20/boot/boot.cmd` пакуется в `boot.scr`.

## 7. Что нужно сделать сейчас (порядок)

1. **Проверить карту и расширить ROMS.** Карта в картридере: `Get-Disk` → найти
   `Generic STORAGE DEVICE` 53 745 811 456 B (номер диска меняется, ориентируйся на размер и
   имя). Затем в elevated-сеансе:
   ```
   python tools\expand_gpt.py --target \\.\PhysicalDriveN
   ```
   Ожидаемо: `expand: partition 5 grew by … MiB`, резервная GPT в конце карты, ROMS ≈ 45 ГиБ.
   Без этого игры некуда копировать, но **на загрузку это не влияет** — можно пропустить.
2. **Вставить карту в консоль** (картридер не подойдёт — загрузка только из слота).
3. **Включить** и смотреть экран 10–20 секунд. Ожидаемо: строки ядра (`Booting Linux on
   physical CPU 0x0…`), затем монтирование squashfs, затем лончер.
4. **Снять факты** в зависимости от сцены:
   - есть текст ядра → сфотографировать/записать последнюю строку;
   - чёрный экран, но подсветка серая → ядро/загрузчик, смотреть UART (`tools/usb-shell.ps1`
     ищет COM-порт, либо любой терминал 115200 8N1);
   - вообще нет реакции (только красный LED) → питание/батарея.
5. **Если экран чёрный** — выключить, вынуть карту, вставить в картридер и прочитать отчёт
   прямо с карты (нужен elevated-сеанс):
   ```
   python tools\read-report.py --target \\.\PhysicalDriveN --out build\device-report
   ```
   Смотреть `build\device-report\checks.txt` (`verdict`, `panel`, `data`, `mem_available_mb`,
   `soc_c`) и `boot.txt`, `dmesg.txt`, `temps.txt`.
6. **По результату:** если ядро дошло до `Run /sbin/init`, а лончер не появился — разбирать
   `rcS`/`inittab`/`launcher --selftest` по отчёту; если ядро не начало грузиться — сверять
   загрузочную цепочку (донорская область, `boot.scr`, `extlinux`).
7. Каждую правку закрывать: host-тест → пересборка → `preflight` → `verify-image` →
   запись `tools\dpflash.py --image … --target \\.\PhysicalDriveN --expect-sha256 … --expand`
   (или `flash-deepos.ps1 -Fresh` в elevated-сеансе) → новая попытка.

## 8. Грабли, на которые уже наступали (не повторять)

- **UAC на русской Windows**: `IsInRole("Administrator")` даёт `False` даже под админом.
  Используй `[Security.Principal.WindowsBuiltInRole]::Administrator` или SID `S-1-5-32-544`.
- **`dpflash` ошибки**: `win32=21` — картридер отвалился (нужен повтор/переоткрытие),
  `win32=32` — Windows держит том после `Clear-Disk` (снять разделы, `Update-HostStorageCache`,
  пауза), `win32=5` — на диске смонтирован том (лечится записью таблицы последней).
- **Скорость записи**: дешёвый картридер + консоль на одном USB-хабе дают 5–8 МБ/с и обрывы.
  Помогает `DEEPOS_CHUNK_KIB=512 DEEPOS_THROTTLE_MS=25`, отключение консоли от ПК на время
  записи, и отказ от `--resume` на «грязной» карте (`-Fresh`).
- **GPT**: CRC заголовка считается по `header_size` (92 байта), не по 512; массив записей
  занимает `128×128/512 = 8` секторов (раньше ошибочно брали 32 и портили `last_usable`).
- **Метки разделов**: имя GPT — UTF-16LE в 72-байтовом поле, обрезать по первому `\x00`
  (а не по `\x00\x00`), иначе получаешь `'B'` вместо `BOOT`.
- **Vendor U-Boot**: собирать **без** `ARCH=arm` (иначе нет SPL), `KCFLAGS=-Wno-error`
  (падает на `common/edid.c`), BL31 — ELF из `rkbin` (`rk3326_bl31_v1.37.elf`) и нужен
  `python3-pyelftools` для `make_fit_atf.py`.
- **BusyBox lean**: `CONFIG_TC` не собирается против заголовков 6.x (`struct tc_cbq_wrropt`) —
  исключён; cron/syslog/klogd выключены ради памяти.
- **PowerShell 5.1**: нет `||`, `.Replace("`n")` в одинарных кавычках вставляет литералы,
  скрипты с кириллицей требуют UTF-8 BOM, длинные docker-команды ломаются на кавычках —
  используй `--entrypoint /bin/bash` и файлы-скрипты.
- **Быстрая проверка «не потерял ли правку»**: рендеры для глаз делает только
  `sh tests/ci/render-all.sh`, `tests/run.py` пишет во временный каталог.

## 9. Правила репозитория

- Ветка `main`; каждый логический шаг — отдельный коммит с префиксом `feat|fix|docs|test|chore`.
- Перед коммитом: `sh tests/run-all.sh`, `make preflight`, `tools/check-secrets.ps1`
  (иначе хук заблокирует), обновление `docs/journal.md` и `docs/metrics.md`.
- Секреты, IP-адреса устройств, токены и пути пользователя в git не попадают.
- Документация по-русски, код и комментарии по-английски.

## 10. Критерий готовности этого захода

1. Консоль включается с карты и показывает лончер DEEPoS (или понятный текст ошибки на
   экране/UART).
2. `BOOT/report/checks.txt` содержит `verdict=ok`, `panel=connected`, `data=rw`,
   `mem_available_mb` ≥ 400, `soc_c` < 70 в простое.
3. Кнопки/стики работают, «Игры → Порты → demo.sh» запускается и выходит по B.
4. Настройки меняются с экрана и сохраняются в `DATA/config/settings.toml`.
5. Образ и код в `<repo>` и на GitHub, журнал/метрики обновлены, тесты зелёные.

Если на каком-то шаге выяснится, что нужна пересборка ядра/DTB — исходники и конфиги уже
лежат: `board/r36s-v20/{dts,linux.config,busybox.config,rootfs-overlay,boot,layout.json,data}`,
`tools/build-kernel.sh`, `tools/build-dtb.sh`, `tools/build-rootfs.sh`.
