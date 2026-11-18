# R36S — подключение, прошивка, работа в системе, батарея, нагрев

Консоль: **Game Console R36S**, SoC **Rockchip RK3326** (4× Cortex-A35), GPU Mali-G31 MP2,
1 ГБ DDR, экран 640×480, батарея Li-Po 3500 мА·ч по наклейке (в прошивках фигурирует 3200 мА·ч),
**eMMC нет** — система целиком живёт на microSD. Значит: «кирпич» = испорченная карта, а не железо.

Полезные общие данные по железу: <https://arch-r.io/docs/features/>

---

## 0. Самое первое: образ стоковой карты (15 минут, спасает вечер)

Стоковая карта — единственный источник `rk3326-r36s-linux.dtb` **твоего** экрана и панели.
Клоны R36S (K36, GR36, Y3506/Soysauce и т.п.) имеют разные матрицы: без своего DTB новая
прошивка даст чёрный или «рассыпанный» экран.

Windows:
1. Карта в картридер, `Win32DiskImager` → в поле Image File путь `<repo>\stock-r36s.img`,
   справа выбрать букву карты → **Read**. (Не «Write» — это затрёт карту.)
2. Открыть FAT32-раздел карты (виден в Проводнике) и скопировать оттуда `*.dtb` в `rs36\stock-dtb\`.
3. Только после этого можно писать что-то другое на карту.

Linux/WSL: `sudo dd if=/dev/sdX of=stock-r36s.img bs=4M status=progress conv=fsync`

Карту лучше сразу заменить на нормальную 32–64 ГБ A1/A2 (Kingston/Samsung/SanDisk), стоковая
часто умирает через месяцы. Оригинал положить в ящик — это и бэкап, и откат.

---

## 1. Каналы подключения

| Канал | Что даёт | Что нужно |
|---|---|---|
| **microSD + картридер** | прошивка, правка загрузчика/оверлеев/kernel cmdline, бэкап | картридер (почти всегда есть) |
| **USB-C → ПК (gadget-сеть) + SSH** | полноценный root-shell, `dmesg`, sysfs, pacman, scp/rsync — всё «в ядре» | дата-кабель, прошивка с USB-gadget (Arch-R, ROCKNIX), включённый SSH на консоли |
| **USB Wi-Fi/Ethernet-донгл** | тот же SSH, но без провода к ПК | донгл (RTL8188EU и подобные), Wi-Fi/роутер |
| **UART (пайка)** | консоль загрузчика, отладка ядра на самом раннем этапе | USB-TTL 3.3 В, 1.5 Мбод, точки на плате — только если очень надо |

Порядок разумный: **карта → прошивка → USB-сеть/SSH**. Wi-Fi у R36S нет (кроме части клонов с RK915).

---

## 2. Прошивка

Варианты (все ставятся на microSD, ничего не «зашивается» в железо):

- **Arch-R** — Arch Linux, ядро **6.12 LTS**, systemd, pacman; самый удобный для «покопаться»
  (USB-сеть из коробки, SSH, сборка своего ядра в Docker). <https://arch-r.io/docs/installation/>
- **ArkOS / dArkOS (AeolusUX)** — Debian-подобная, «народный стандарт» для R36S, много гайдов:
  <https://github.com/AeolusUX/ArkOS-R3XS/releases>
- **ROCKNIX** — ядро 6.12, оверлеи экрана совместимы с Arch-R (одна и та же схема generic-dsi).

Порядок для Arch-R:
1. `ArchR Flasher` (Windows .msi) с <https://github.com/archr-linux/archr-flasher/releases>
   либо balenaEtcher + образ `ArchR-R36S.aarch64-<дата>-original.img.gz`
   (**original** — обычный R36S; **clone** — K36/RGB10X/XU-Mini-M и подобные; Soysauce — образ original).
2. Панельный оверлей: <https://arch-r.io/overlay-generator> (или офлайн `archr-dtbo-offline.zip`),
   на вход — **свой** `rk3326-r36s-linux.dtb` из п.0:
   ```
   python archr_dtbo.py rk3326-r36s-linux.dtb SDORIG -o mipi-panel.dtbo
   ```
   Файл кладётся на FAT32-раздел как `overlays/mipi-panel.dtbo` (имя фиксировано в `extlinux.conf`).
   Если консоль слабая/перезагружается — вариант `Safe` (`--safe-cpu`, 1296 МГц).
3. Первый запуск: авто-расширение раздела + перезагрузка, второй запуск — лаунчер.

Чёрный экран после логотипа = неверный/отсутствующий оверлей, а не «сдохла».

---

## 3. SSH без Wi-Fi: USB-кабель вместо сети

На консоли: **Settings → Network → Network services → SSH = ON**, там же сменить root-пароль.
Затем **Settings → Network → Network services → USB → функция gadget = «Интернет от ПК»**
(на старом Windows 10 включить «совместимость с Windows 10» — переключит NCM → RNDIS).

На ПК (Windows): `Win+R` → `ncpa.cpl` → правой кнопкой по адаптеру с интернетом (Wi-Fi) →
Свойства → Доступ → «Разрешить другим пользователям…» → домашняя сеть = новый Ethernet-адаптер
консоли (`UsbNcm` / `Remote NDIS`). Windows выдаст консоли адрес `192.168.137.x`.

```
ssh root@<console-ip>        # пароль по умолчанию в Arch-R: archr
# без ICS консоль поднимает фиксированный адрес:
ssh root@<console-ip>
```
Проверка с ПК: `.\check-usb.ps1` (лежит рядом).

Файлы: `scp rom.sfc root@<console-ip>:/storage/roms/snes/`, массово — `rsync -avh`,
графически — Samba (в Arch-R включается в меню) или `sftp://root@<console-ip>/storage/roms/`.

Wi-Fi-донгл как альтернатива: `ssh root@<ip>` (IP в Settings → Network → Wi-Fi),
в ArkOS логин `root` / `arkos`.

---

## 4. Работа «в системе/ядре»

```bash
# температура и точки троттлинга
for z in /sys/class/thermal/thermal_zone*; do echo "$z $(cat $z/type) $(cat $z/temp)"; done
grep . /sys/class/thermal/thermal_zone0/trip_point_*_{temp,type}
# вентиляторы/кулеры (пассив): cooling_device*
grep . /sys/class/thermal/cooling_device*/type

# CPU
cat /sys/devices/system/cpu/cpufreq/policy0/scaling_available_governors
cat /sys/devices/system/cpu/cpufreq/policy0/scaling_available_frequencies
cat /sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq
echo ondemand    | sudo tee /sys/devices/system/cpu/cpufreq/policy0/scaling_governor
echo 1008000     | sudo tee /sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq
cat /sys/devices/system/cpu/cpufreq/boost     # 1 = турбо 1512 МГц включено
echo 0           | sudo tee /sys/devices/system/cpu/cpufreq/boost

# GPU (mali/panfrost через devfreq)
ls /sys/class/devfreq/; cat /sys/class/devfreq/*/available_frequencies
echo 400000000 | sudo tee /sys/class/devfreq/*.gpu/max_freq

# память/шина
cat /sys/class/devfreq/*dmc*/cur_freq

# батарея
ls /sys/class/power_supply/
for f in status capacity health voltage_now current_now charge_full charge_full_design charge_counter; do
  printf '%-20s %s\n' "$f" "$(cat /sys/class/power_supply/rk817-battery/$f 2>/dev/null)"; done

# журналы
dmesg | grep -iE 'rk817|thermal|throttl|cpufreq|vdd_arm|mali|panfrost'
journalctl -b -p warning
```

Ядро и сборка: Arch-R собирается в Docker (`make docker-RK3326`), правится
`projects/ArchR/devices/RK3326/linux/linux.aarch64.conf` (опции ядра) и
`.../patches/linux/000-rk3326-dts.patch` + `.../linux/dts/rockchip/rk3326-gameconsole-r3xs.dtsi`
(OPP, напряжения, регуляторы). См. <https://arch-r.io/docs/build/> и
<https://arch-r.io/docs/technical/>.

Закрепить настройку после ребута (Arch-R): systemd-unit либо каталог автостарта прошивки.

```bash
sudo tee /etc/systemd/system/cpu-cap.service >/dev/null <<'EOF'
[Unit]
Description=Cap CPU for heat/battery
After=multi-user.target
[Service]
Type=oneshot
ExecStart=/bin/sh -c 'echo ondemand > /sys/devices/system/cpu/cpufreq/policy0/scaling_governor; \
 echo 1008000 > /sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq; \
 echo 0 > /sys/devices/system/cpu/cpufreq/boost'
[Install]
WantedBy=multi-user.target
EOF
sudo systemctl enable --now cpu-cap.service
```

Если под «ядром» имелись в виду **ядра эмуляторов** (libretro cores): в RetroArch
per-core overrides — 1× разрешение, shaders off, run-ahead off, rewind off, frameskip для
PSP/Dreamcast/N64; тяжёлые системы лучше отдельными standalone-сборками (PPSSPP, Flycast, Mupen64Plus).

---

## 5. Батарея: как измеряется и как калибровать

Замер — **топливомер внутри PMIC RK817** (`rk817-battery` + `rk817-charger`), кулоновский счётчик,
а не «по вольтажу». Отсюда все типичные болячки: проценты прыгают, падают с 40 % до 0,
«100 %» держится час, а потом обвал.

Порядок:
1. **Обновиться** до сборки с исправленным `rk817_charger` (Arch-R ≥ 2.0-rc2; свежий ArkOS/dArkOS).
   Там закрыты порча калибровки при suspend/resume и пересчёт FCC. <https://arch-r.io/docs/update/>
2. Калибровочный цикл (без вскрытия):
   - зарядить до 100 % и **оставить на зарядке ещё 1–2 ч** (топпинг, счётчик синхронизируется на полном);
   - отключить, дать остыть;
   - разрядить в играх **до автоотключения** (защита сработает сама, в 0 В не уйдёт);
   - сразу, без пауз, зарядить до 100 % — счётчик выучит реальную ёмкость.
3. Смотреть `charge_full` vs `charge_full_design` (мкА·ч). Если `charge_full` заметно ниже
   (изношенная банка) — в свежих ядрах `charge_full` **доступен на запись**:
   ```
   echo 2800000 | sudo tee /sys/class/power_supply/rk817-battery/charge_full
   ```
   Значение — измеренная ёмкость в мкА·ч (2 800 000 = 2800 мА·ч). Это делает проценты честнее;
   задирать выше реальной ёмкости нельзя — консоль будет выключаться «на 15 %».
4. Не включается после долгого лежания — не паниковать: 30–60 мин на зарядке (защита глубокого
   разряда), в крайнем случае передёрнуть разъём батареи.
5. Не держать сутками на 100 % и не играть в тяжёлое на зарядке — греются и банка, и зарядник.

---

## 6. Нагрев: софт (быстро, бесплатно) и железо (мод)

Сначала измерь, потом крути: 20 минут одного и того же PSP-тайтла,
`watch -n1 'cat /sys/class/thermal/thermal_zone0/temp'` (миллиградусы).

**Софт** (снижает температуру без паяльника):
- губернатор `ondemand`/`schedutil` вместо `performance`; `scaling_max_freq` 1008–1296 МГц
  (полная шкала 408 / 816 / 1008 / 1416 / +1512 турбо);
- **турбо выключить** (по умолчанию выключено; включённое = +0.05 В и больше тепла);
- GPU: `max_freq` 400 МГц для 8/16-бит, 650 МГц только для PSP/Dreamcast/N64;
- экран: яркость 40–60 % (подсветка греется не меньше SoC);
- RetroArch: 1× разрешение, shaders off, run-ahead off, rewind off, frameskip 1–2 на тяжёлом;
- не запускать скрапер/синк/Samba во время игры (Arch-R сам глушит 4 сервиса);
- тяжёлые игры — не на зарядке.

**Железо** (аккуратно, консоль разбирается винтами с задней крышки, часть под наклейками):
- термопрокладка 1–1.5 мм (6–12 Вт/м·К) или медная пластина 0.5–1 мм + прокладка между
  экраном SoC и задней крышкой — тепло уходит в корпус;
- аккуратно: не пережать плату и не давить на экран, металл **не** над аккумулятором;
- вентиляционные отверстия в задней крышке над зоной SoC (не над батареей) — самый эффективный
  пассивный мод;
- **не** ставить микро-вентилятор: места нет, воздуховода нет, шум и лишний расход;
- алюминиевый/перфорированный корпус-чехол — по желанию.

Термотроттлинг ядро делает само (trip points, см. п.4); после мода проверь, что температура
в том же сценарии стала ниже, а не «стало казаться».

---

## 7. Что ещё улучшить по мелочи

- Карта microSD: A1/A2, 32–64 ГБ, ext4-раздел не трогать при выключенной консоли.
- BIOS/прошивки эмуляторов (PSX/N64/NDS) — из проверенного набора, иначе часть игр не стартует.
- PortMaster — нативные порты (нужны `lzma`, `xdelta3`, `squashfs` — в Arch-R уже есть).
- Samba/Syncthing для заливки ROM и сейвов без дёргания карты.
- Отключить неиспользуемое: Bluetooth, лишние сервисы, скрапер.
- Панельный оверлей и `extlinux.conf` держать в бэкапе вместе с образом карты.

---

## Источники

- Arch-R: установка, SSH, USB-интернет, турбо, сборка — <https://arch-r.io/docs/installation/>,
  <https://arch-r.io/docs/ssh/>, <https://arch-r.io/docs/usb-internet/>,
  <https://arch-r.io/docs/overclock/>, <https://arch-r.io/docs/build/>
- Arch-R release notes (патчи rk817, CHARGE_FULL, OPP) — <https://github.com/archr-linux/Arch-R/releases>
- ArkOS R3XS (dArkOS) — <https://github.com/AeolusUX/ArkOS-R3XS/releases>
- Патчи rk817_charger (FCC/калибровка) — <https://marc.info/?l=linux-pm&m=172736186710255&q=mbox>
