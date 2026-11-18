# План тестирования DEEPoS на реальной консоли (R36S-V20)

Документ для этапа 2: проверка собранного образа на клоне `R36S-V20 2025-05-18`.
Пока консоль не подключена, все проверки ниже — ручные по чек-листу; автоматические
тесты (host) уже покрывают раскладку образа, протоколы модулей, хранилище сейвов,
сборку DTS и конфигов.

## 0. Что должно быть готово до прошивки

| Артефакт | Путь | Проверка |
|---|---|---|
| Образ карты | `build/deepos-r36s-v20.img` | `sha256sum` совпадает со значением из `docs/metrics.md` |
| Загрузчик | `build/uboot/idbloader.img`, `build/uboot/u-boot.itb` | `tools/build-uboot.sh` → `BUILD.txt` |
| Ядро | `build/kernel/Image` | 74 490 368 B, версия 6.12.56 |
| DTB платы | `build/kernel/rk3326-r36s-v20.dtb` | 46 564 B |
| Rootfs | `build/rootfs.squashfs` | размер и число записей — в `docs/metrics.md` |

Образ без загрузчика не загрузится: `idbloader.img` пишется по смещению 32 KiB,
`u-boot.itb` — по 8 MiB (Rockchip boot chain), это делает `tools/mkimage.py --loader`.


### 0.4a Проверка готовности (preflight)

    python3 tools/preflight.py --root .

Проверяет то, что нужно именно загрузке: размер ядра, `compatible` нашего DTB,
имя DTB в `extlinux.conf` = файл в `BOOT/dtbs`, sha256 `BOOT/KERNEL` = `MANIFEST.json`,
все бинари и бит `x` на `etc/init.d/rcS`, наличие загрузчиков, и в конце гоняет
`tools/verify-image.py`. Ожидаемая строка: `PREFLIGHT: GO (32 checks)`.
**Если NO-GO — карту не писать.**

## 0.4 Проверка образа до записи (обязательно)

Перед записью на карту образ проверяется офлайн — без карты и без прав администратора:

```sh
python3 tools/verify-image.py --loader build/uboot build/deepos-r36s-v20.img
```

Ожидаемый вывод: `PASS  verify-image: 39 checks`. Проверяются CRC первичного и резервного
GPT, геометрия разделов, сигнатуры файловых систем, побайтовая раскладка загрузчика
(`idbloader.img` на 32 KiB, `u-boot.itb` на 8 MiB), содержимое `BOOT` (`KERNEL`, dtb,
`extlinux.conf`, `MANIFEST.json` со sha256) и обязательные файлы корневой системы внутри
squashfs. Если проверка падает — образ не писать.

## 0.5. Смоук-тест после первого буста

Первое, что стоит запустить на устройстве — встроенный отчёт об окружении:

```sh
/usr/bin/launcher --selftest
```

Ожидаемые строки (ключ=значение, парсится глазами и скриптом):

| Строка | Что значит | Норма на R36S-V20 |
|---|---|---|
| `version=0.4` | версия лаунчера | совпадает с `docs/metrics.md` |
| `roms=… systems=N games=M` | найдены системы и игры | `systems>0` при непустом ROMS |
| `data=… continue=N` | прочитанный `continue.tsv` | `N` равно числу строк файла |
| `emulators=… emulators_present=1` | найден `emulators.toml` | 1 |
| `modd=… modules=N` | связь с супервизором | `N` = число модулей в `/storage/.config/deepos/modules` |
| `fb=… fb_present=1` | фреймбуфер | 1 (иначе смотреть `CONFIG_DRM_FBDEV_EMULATION`) |
| `input_events=N` | устройства ввода | ≥1 (`gpio-keys` и/или `adc-joystick`) |
| `status=ok` | отчёт дошёл до конца | ok |

Если `input_events=0` — кнопки не заведены: проверить `dmesg | grep -i key` и DTS
(`gpio-keys`/`adc-joystick`). Если `fb_present=0` — нет `/dev/fb0` (fbdev emulation).

## 1. Бэкап текущего состояния

1. Снять полный образ стоковой/рабочей карты (Arch-R) через Win32DiskImager Read
   или `dd` на Linux; сохранить `*.img.gz` + `sha256`.
2. Скопировать `BOOT` и `ROM-раздел` папками (быстрее восстановить отдельные файлы).
3. Записать в журнал версию Arch-R (`archr-update version`), ядра (`uname -r`) и
   модель панели из `/proc/device-tree/model`.

## 2. Прошивка

```powershell
# карта в картридере, диск определить через Get-Disk (например, PhysicalDrive2)
python tools/dpflash.py --image build/deepos-r36s-v20.img `
    --target \\.\PhysicalDrive2 --expect-sha256 <sha256> --dry-run
python tools/dpflash.py --image build/deepos-r36s-v20.img `
    --target \\.\PhysicalDrive2 --expect-sha256 <sha256>
```

`dpflash` пишет таблицу разделов **последней**: пока таблица пуста, Windows не
монтирует FAT/exFAT, и запись не падает с `win32=5`. После записи — `sync`,
извлечь карту, вставить в консоль.

## 3. Первый буст — что должно произойти

1. U-Boot SPL → `u-boot.itb` → `extlinux.conf` с `LABEL DEEPoS`.
2. Ядро монтирует `LABEL=DEEPOS_A` (squashfs, ro), `rcS` монтирует `/data` (p3)
   и `/storage` (p4), запускает `mdev`, затем `launcher` на tty0.
3. Экран: чёрный фон, вкладки «Продолжить · Игры · Настройки · Модули · Файлы ·
   Сведения», статус-бар с часами и батареей.
4. Если экран тёмный, а UART на гребёнке (115200, `console=ttyS2,1500000`) что-то
   печатает — смотреть причину в логе ядра; частые причины: неверный `FDT`
   (панель), отсутствующий `simple-battery`, `root=LABEL` не найден.

## 4. Чек-лист приёмки (отмечать по факту)

- [ ] Панель: картинка без полос, разрешение 640×480, поворот 0.
- [ ] Подсветка: 46 уровней, `default-brightness-level = 38`, регулировка работает.
- [ ] Кнопки: 16 GPIO-кнопок, A/B в правильном порядке (оверлей `ABs` не нужен —
      DTS сразу описывает физическую раскладку).
- [ ] Стики: 4 аналоговых оси, мёртвая зона не «плывёт», fuzz/flat работают.
- [ ] Громкость: качелька ADC, звук в динамике (spk-con-gpio gpio3 7).
- [ ] Питание: `battery` в sysfs, проценты меняются, зарядка видна при кабеле в
      гнезде CHARGE (OTG — только данные).
- [ ] Нагрев: простой ≤55 °C, стресс 4 потока 5 мин ≤85 °C, троттлинг срабатывает.
- [ ] Память: `MemAvailable` в простое ≥560 МБ, `MemTotal` ≈732 МБ.
- [ ] Загрузка: ≤12 с до первого кадра (секундомер по UART: `Startup finished`).
- [ ] A/B: `update.py begin` 4 раза → слот переключился и `rollback=true`.
- [ ] Модули: `modd` стартует, `thermal` показывает температуры, `saves` делает бэкап.
- [ ] Samba/USB: `smbd` поднимается, `\\deepos\...` виден с ПК; gadget NCM даёт
      SSH root@deepos.local.
- [ ] Сейвы: `saved put` → перезагрузка → `saved get` возвращает тот же файл.

## 5. Если что-то пошло не так

| Симптом | Что проверить |
|---|---|
| Нет картинки, UART молчит | загрузчик: смещения `idbloader`/`u-boot.itb`, питание карты, целостность `BOOT` |
| UART есть, экран тёмный | DTB/панель: `panel@0` compatible, `reset-gpios`, тайминги, `dsi,lanes` |
| `root=LABEL` не найден | GPT: метки `DEEPOS_A`, размер squashfs, `mkimage` не обрезал раздел |
| Экран есть, лаунчер падает | `journalctl` нет (нет systemd) → смотреть `/tmp/launcher.log`, свободную RAM, размер шрифтов |
| Троттлинг раньше 85 °C | `thermal_zone` trip-точки, `cooling-maps`, термопрокладка |
| Кнопки перепутаны | `gpio-keys` code/GPIO в DTS, `linux,code` из `linux-event-codes.h` |

## 6. Возврат на Arch-R

Образ Arch-R (`images\ArchR-clone.img.gz`, 1.6 ГБ) + оверлей панели остаются в
локальной папке проекта: перепрошить тем же `dpflash.py` или Etcher,
вернуть оверлей `mipi-panel.dtbo` и настройки из бэкапа. Данные ROM лежат на
отдельном exFAT-разделе, при перепрошивке их нужно сохранить заранее.

## 7. Отчёт с устройства (после первого буста)

Собрать факты в один файл, чтобы сравнивать с host-эталоном из `docs/PROTOTYPE-STATUS.md`.
Команды выполняются на консоли (UART или SSH через USB-NCM, `root@deepos.local`):

```sh
# 1. Базовая готовность
/usr/bin/launcher --selftest

# 2. Диски и монтирования
cat /proc/mounts
df -h

# 3. Память (цель: MemAvailable >= 560 МБ, MemTotal ~732 МБ)
free -m
cat /proc/pressure/memory

# 4. Температуры и частоты
for z in /sys/class/thermal/thermal_zone*/type; do echo "$z: $(cat $z) $(cat $(dirname $z)/temp)"; done
cat /sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq
cat /sys/devices/system/cpu/cpufreq/policy0/scaling_governor

# 5. A/B и модули
/usr/bin/updatr --state /data --boot /flash status
/usr/bin/modd --help >/dev/null 2>&1; echo "modd: $?"
ls /data/modules

# 6. Питание
grep . /sys/class/power_supply/battery/{status,capacity,voltage_now,charge_full,charge_full_design}

# 7. Загрузка (что успело сказать ядро и rcS)
dmesg | grep -iE "mmc|panel|st7703|rk817|gadget" | head -40
dmesg | head -3
```

Прислать вывод целиком — по нему заполняется `docs/device-report.md`:

| Что | Эталон host | Факт на устройстве |
|---|---|---|
| `launcher --selftest` | `status=ok`, `systems=…`, `data_ok=1`, `roms_ok=1` | |
| Загрузка до первого кадра | ≤ 12 с | |
| `MemAvailable` в простое | ≥ 560 МБ (Arch-R: 414–468) | |
| Простой, °C | 48–53 | |
| Стресс 4 потока 45 с, °C | 1296 → ~70, 1416 → 79.6 | |
| Троттлинг | порог 85 °C | |
| A/B | `attempts=0..2`, слот A | |
| `modd` + модули | thermal/saves в списке | |

Если расхождение по экрану/кнопкам/звуку — сначала смотреть таблицу «Если что-то пошло
не так» (§5), затем присылать `dmesg` и `--selftest`: по этим двум выводам видно,
DTB-проблема это, драйвер панели или userland.
