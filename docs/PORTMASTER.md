# PortMaster на DEEPoS

PortMaster доступен в сборке R36S‑V20 с опциональным пакетом. Он запускается
из меню игр и закрывается вместе с библиотеками и Python. При первом открытии
он подготавливает рабочий каталог на DATA. Порты устанавливаются на ROMS
карты TF1, в папку `ports/`.

## Открыть на консоли

1. Загрузите DEEPoS и проверьте дату и время в «Настройках». Верная дата
   нужна для подключения по HTTPS.
2. Откройте **Игры → Порты → PortMaster**. Для каталога и загрузок
   подключите консоль к сети через OTG с доступом в интернет.
3. Выберите порт и нажмите **Install**. После выхода PortMaster обновляет
   список портов в DEEPoS.
4. Если порт требует файлы оригинальной игры или отдельный runtime,
   следуйте инструкции на странице конкретного порта.

Для офлайн-установки скачайте архив порта на ПК и положите его целиком в
`ROMS/ports/autoinstall/`. Откройте PortMaster на консоли, чтобы он обработал
архив. [Каталог](https://portmaster.games/games.html) ·
[Установка портов](https://portmaster.games/installation/installing-ports/) ·
[Среды исполнения](https://portmaster.games/installation/runtimes/)

На обычной сборке без опционального пакета пункт PortMaster появляется после
установки системного образа с этим пакетом. Установщик upstream для ArkOS
и других поддерживаемых систем использует их раскладку каталогов.

## Пакет для сборки

Проект использует официальный `PortMaster.zip` от 2026.11.17-0700 и
ARM64-компоненты из локального донора Arch‑R Clone. Подготовка выполняется
в контейнере `deepos-cross:local`. Архив upstream лежит в его
[релизе на GitHub](https://github.com/PortsMaster/PortMaster-GUI/releases/tag/2026.11.17-0700).

В контейнере выполните:

```sh
python3 tools/package-portmaster.py \
  --donor /path/to/ArchR-clone.img.gz \
  --upstream /path/to/PortMaster.zip \
  --out build/deepos-portmaster-aarch64.tar.gz

PORTMASTER_PACKAGE="$PWD/build/deepos-portmaster-aarch64.tar.gz" \
  sh tools/build-rootfs.sh
```

Пакет содержит Bash, Python и библиотеки SDL, Mesa и ALSA, которые нужны
при запуске PortMaster или порта. Лаунчер передаёт стандартные порты в это
окружение, сохраняя пользовательские команды из `emulators.toml`.
Журнал менеджера находится в `/data/portmaster/PortMaster/log.txt`.
Место установки, управление, сеть и совместимость конкретных портов
проверяются на устройстве. Первый тест целесообразно проводить с портом
AArch64 из категории *Ready to Run*.

[На главную](../README.md) · [Установка прошивки](INSTALL.md) ·
[Разработка](DEVELOPMENT.md)
