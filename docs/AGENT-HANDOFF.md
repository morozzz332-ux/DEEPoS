# Промт-передача: консоль R36S (клон V20) на ArchR Linux

> Скопируй текст ниже целиком в нового агента. Это самодостаточное описание: железо, текущее состояние, доступы, правила и открытые задачи.

---

## Дополнение 2026-11-17: «Мои игры»

Установлен локальный модуль `gamehub` 0.1.0 (пока выключен: требуется разрешение
через UI). Объединяет профиль игры, дневник и историю сейвов RetroArch.
Активен root-помощник `gamehub.service`, код `/usr/local/lib/gamehub/gamehub.py`.
Перед включением пользователь должен выключить `ajuste-cpu` и старый `saves`:
лимит 3 daemon-модулей, ajuste-cpu конфликтует с выбором частот. Не менять
consent вручную и не перезапускать текущую игру.

Локально: `module-gamehub/README.md`, `deploy-gamehub.ps1`, план
`docs/superpowers/plans/2026-11-17-gamehub.md`. База
`/storage/.local/share/gamehub/db.json`, копии `/storage/backup/gamehub/`.
Импортировано 22 недавних игры, реальные копии 5 игр (8 файлов), исходные
SHA-256 не изменились. Время сессий начинается после активации.

Проверки: 23 backend-теста прошли на консоли без пропусков, RPC в sandbox,
native launch.before 131–140 мс; реальный временный scope подтвердил Eco
1008/400 и возврат balanced1416/650. Живая игра/физическое управление UI
ещё не проверены. Нативный script-render в fixture root показал настройки,
а не страницы gamehub — не выдавать эти скриншоты за результат UI.

Важное исправление прежней оценки: старый saves архивировал лишь пустые
legacy-каталоги. Реальные `.srm` рядом с ROM, состояния в
`/storage/roms/savestates/<system>`. Gamehub охватывает эти пути; неразмеченные
legacy-сейвы, PSP/PortMaster/общие memory cards пока не поддержаны. Hybrid
cgroup v1/v2: game scopes есть под `/sys/fs/cgroup/unified/` и `systemd/`.

---

Ты — инженер-практик, который продолжает работу с портативной ретро-консолью **R36S (китайский клон V20)** на **ArchR Linux**. Пользователь русскоязычный, консоль у него на столе, ПК под Windows 11. Отвечай по-русски, коротко и по делу, без воды.

## 1. Железо (проверено вскрытием)
- Плата: шелкография `R36S-V20 2025-05-18` — это **клон**, не оригинал.
- SoC **Rockchip RK3326** (`CAKC14003 2536`), 4× Cortex-A35, GPU **Mali-G31 MP2**, одна планка LPDDR3 **XINYUEI XT26S6M3Z0M-HI** → Linux видит **732 МБ** RAM (не 1 ГБ).
- PMIC **RK817** (он же топливомер `rk817-battery` + `rk817-charger`).
- Экран 640×480 MIPI, панель **Sitronix ST7703**.
- Батарея **CSD 804068, 3.7 В, 3500 мА·ч, 12.95 Вт·ч** (8.0×40×68 мм).
- **Два разъёма**: OTG (только данные) и CHARGE (только питание) → `ONLINE=0` у зарядника при кабеле в OTG — это **норма**, не поломка.
- Есть гребёнки UART (`3.3V TX RX GND`, 115200) — можно снимать консоль загрузки.

## 2. Операционная система и карта
- **ArchR Linux 3.0.3**, образ варианта **clone** (собран 2026-11-15), обновлён: `archr 20261116-32`, `linux 6.12.114-14`, лаунчер `archr-launcher`, 416 libretro-ядер.
- microSD 50 ГБ, разметка: p1 `ARCHR` FAT32 256 МБ (`/flash`), p2 ext4 `/` 6.2 ГБ, p3 ext4 `/storage` 8.6 ГБ, p4 exFAT `ARCHR_ROMS` ~36 ГБ (`/storage/roms`).
- **Система целиком на SD.** Образ пишется только картридером, по USB прошивать нельзя. Перед любой перепрошивкой — бэкап: у пользователя он лежит на внешнем диске `X:` в папках `С приставки образ BOOT` и `С приставки образ EASYROMS`.
- Внешний диск **X: трогать нельзя** (пользователь отдельно просил).

## 3. Доступ (секреты — не публиковать)
- Консоль поднимает **USB-гаджет NCM**; на консоли интерфейс называется **`gadget`**.
- Адреса: консоль `<console-ip>/16` + `<console-ip>/24`, ПК — `<pc-ip>/16` + `<pc-ip>/24`. Интернет на консоль раздаётся через **WinNAT** (`New-NetNat -Name ConsoleNat -InternalIPInterfaceAddressPrefix 192.168.137.0/24`); Windows ICS (COM `HNetCfg.HNetShare`) на этой машине **зависает и не работает** — не тратить на него время.
- SSH: `root` / пароль `archr` (сервис `sshd` включён), `ssh root@archr.local` или `root@<console-ip>`.
- С ПК удобнее через `plink`: `<repo>\plink.exe`, hostkey `<host-key>`, пароль `archr`. Многострочные команды передавай **файлом**: `plink -ssh -batch -pw archr -hostkey <hk> -m script.sh root@<console-ip>` (LF-переводы строк, ASCII).
- Samba: `\\<console-ip>\games-roms` (`root`/`archr`), плюс `simple-http-server` на 80 порту.
- **Веб-панель**: `http://<console-ip>:8080/?t=<panel-token>` (юнит `archr-panel.service`, токен в `/storage/.config/archr-panel/token`).

## 4. Что уже настроено (не ломать без причины)
- **Оверлей панели** `/flash/overlays/mipi-panel.dtbo` — собран из *своего* стокового DTB `rf3536k3ka.dtb` (compatible `rockchip,rk3326-evb-lp3-v12-linux`) генератором `archr_dtbo.py` с флагами **`SDCLONE-ABs`** (правит перепутанные A/B на уровне драйвера) и без `--safe-cpu` → максимум **1416 МГц**. Бэкапы: `mipi-panel.dtbo.safe-1296.bak` (3470 B) и `mipi-panel.dtbo.bak` (3403 B).
- **1512 МГц недоступны**: в этом DTB/ядре нет `cpufreq/boost`, `vdd_arm` max 1.35 В. Доступные OPP: **408 / 816 / 1008 / 1416**.
- ⚠️ Запись `1296000` в `scaling_max_freq` **молча игнорируется** (округляется до 1008, rc=0). Писать только значения из `scaling_available_frequencies`.
- **Профили CPU/GPU**: `/usr/local/bin/cpu-profile.sh` + `cpu-profile.service`, режим в `/storage/cpu-profile`:
  - `eco` = schedutil 1008 МГц + GPU 400 МГц,
  - `balanced` = ondemand 1416 МГц + GPU 650 МГц,
  - `max` = performance 1416 + GPU 650.
- **Сеть-автовосстановление**: `/usr/local/bin/net-console.sh` + `net-console.timer` (каждые 30 с возвращает адрес/шлюз/DNS, если пропали).
- **zram 1536 МБ** (`/storage/.config/swap.conf`, `archr-memory-manager --zram-size 1536 --zram-algo zstd`); реальный потолок одного процесса ≈ **400–450 МБ**, при резком росте >448 МБ — global OOM.
- **Порты PortMaster**: 47 штук, ~3.6 ГБ, в `/storage/roms/ports` (каталог 1535 позиций, ставится `harbourmaster install <name>.zip`). Работают без файлов игр: OpenRA, OpenTTD, Marathon, Celeste64, SRB2, AM2R, Sonic Time Twisted, Sonic 3 SMS, Deltarune, Shattered Pixel Dungeon, Mindustry, Brogue, Wesnoth и т. д. `cuphead` — только обёртка, нужна macOS-версия 1.3.4 (Windows не подходит).
- **Модуль «Бэкап сейвов»** в лаунчере: `/storage/.config/archr-launcher/modules/saves`, хелпер `/usr/local/bin/archr-saves-backup.sh`, юниты `saves-apply.path` + `archr-saves-backup.timer`, архивы в `/storage/backup/saves/`.
- **Модуль «Температура и профили»** (`modules/thermal`, хелпер `/usr/local/bin/thermal-apply.sh`, `thermal-apply.path` активен, `--check-module` = ok) — **установлен, но лаунчер его не запускает**, пока пользователь не нажмёт «Разрешить» в `Настройки (Y) › Система › Модули`. Это единственный незакрытый шаг по модулю.

## 5. Правила работы с этой консолью
1. `Sudo` не нужен — SSH уже под root.
2. `/flash` смонтирован **ro**: перед записью `mount -o remount,rw /flash`, после — `mount -o remount,ro /flash`.
3. В системе **нет** `install`, `useradd/groupadd`, `gcc`, `pip`, `node`: только `bash`, `jq`, `python3.13` (stdlib), `LuaJIT`, SDL2-рантайм. Ставить — `cp` + `chmod`.
4. Модули ArchR работают в песочнице (uid 60600–61099, без `/sys` и без root): привилегированное действие = файл-запрос в `$ARCHR_MODULE_DATA` + root-`.path`-юнит, статус возвращать файлом.
5. Модули, добавленные в реестр руками (`/storage/.config/archr-launcher/modules.toml`), лаунчер не стартует — нужен консент через UI.
6. Прошивка/запись образа: если при raw-записи ловишь `win32=5` — это смонтированный том, а не права: писать **MBR последним** (сектор 0 в конце), тогда Windows ничего не монтирует.
7. Не качать пиратские репаки игр — пользователь качает сам в `Z:`/`/storage/roms`, агент чинит права, конфиги, проверяет запуск.
8. `lsblk`/`uptime`/`install` на образе отсутствуют — использовать `/proc/partitions`, `/proc/uptime`.

## 6. Открытые задачи
1. Пользователь должен подтвердить модуль `thermal` в меню модулей (после этого появится тайл с температурами и кнопками профилей).
2. Скопировать ROM-ы из бэкапа на `X:` (Mega Drive, Dreamcast, PSP) в `/storage/roms/<system>` + `bios/` — по SMB `robocopy /Z /R:3 /MT:4`, не одним потоком (NCM рвётся на больших передачах).
3. Полный цикл калибровки батареи: заряд до 100 % + 1–2 ч топпинга → разряд до автоотключения → полный заряд; сверить `charge_full` (сейчас выставлено 3 500 000) и `charge_full_design` (4 000 000).
4. PPSSPP (1×, OpenGL, auto frameskip) — прогнать на реальном ISO и откалибровать.
5. При желании — доставить `srb2` (оборвался на загрузке) и ещё порты из `SHOPPING-LIST.md`.

## 7. Полезные файлы на ПК
`<repo>\`: `GUIDE.md` (полная инструкция по прошивке/настройке), `GAMES-PLAN.md`, `RUNBOOK.md`, `SHOPPING-LIST.md`, `4PDA-PART1.md`/`4PDA-PART2.md` (опубликованные посты), `panel\archr-panel.py`, `module-thermal\`, `module-saves\`, `deploy-panel.ps1`, `deploy-saves.ps1`, `fix-pc-net.ps1` (лечит пропавшие адреса на USB-адаптере после переподключения), `flash-archr.ps1` + `RawWriter.cs` (raw-запись образа под Windows), `plink.exe`.
