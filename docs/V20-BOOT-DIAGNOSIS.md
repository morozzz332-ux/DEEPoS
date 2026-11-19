# Диагностика загрузки R36S‑V20

При проверке образа 0.26-dev после попытки запуска обе GPT и байты
загрузчика на карте совпали с ожидаемыми. FAT32 содержала `boot.scr`
и extlinux, каталога `BOOT/report` не было. Это оставляет открытыми
этапы до монтирования BOOT.

## Сравнение с открытыми прошивками

- [Arch‑R](https://github.com/archr-linux/Arch-R) выпускает вариант Clone для
  K36 и R36S V20. Из проверенного открытого архива взяты загрузчик, ядро
  Linux 6.12.114 и `rk3326-gameconsole-eeclone.dtb`. Для панели использован
  локальный оверлей, ранее применённый на этой же консоли. Он выбирает
  `archr,generic-dsi` и содержит команды инициализации панели.
- [Порт (d)ArkOS4Clone для RF3536K3KA](https://github.com/reppard/r36s-v20-arkos4clone)
  описывает отличия PX30S от PX30 и использует загрузочную область
  32 КиБ–16 МиБ. Вариант с Linux 5.10 отключает DMC на протестированной им
  ревизии. Прямой перенос этого решения на ядро Arch‑R 6.12 потребовал бы
  отдельного подтверждения.
- [ROCKNIX для EE-клонов](https://rocknix.org/devices/unbranded/EE-clones/)
  использует отдельный образ и оверлей конкретной панели. Описание V20
  нельзя подменять профилем обычной R36S.
- [AURKNIX](https://github.com/lcdyk0517/distribution_aurknix/blob/next/documentation/user_man/USER_MANUAL_en.md)
  также различает аппаратные варианты и использует селектор DTB.
- [Документация U‑Boot для Rockchip](https://docs.u-boot-project.org/en/stable/board/rockchip/rockchip.html)
  подтверждает старт загрузочного блока с LBA 64 и поддерживаемую схему GPT.

## Что обнаружено в DeepOS

В исходном DTB `/vop@ff460000` отключён. Строка `sitronix,st7703` не
сопоставляется с драйвером в собранном Linux 6.12.56. Оба дефекта
достаточны для отсутствия изображения. UART2 в исходном DTS также
отличается от адреса диагностического UART в профиле Arch‑R.

Профиль `archr-v20` использует связку ядра и DTB Arch‑R для этой платы.
Параметр `rdinit=/__deepos_mount_root__` указывает на отсутствующий путь,
поэтому Linux подключает squashfs `DEEPOS_A` и запускает DeepOS
`/sbin/init` вместо `/init` встроенного initramfs Arch‑R.
Профиль задаёт раннюю консоль на адресе UART из DTB.
Для штатного USB ACM требуется поддержка со стороны ядра. Для раннего
журнала этого варианта предназначен UART платы.

## Воспроизведение

В окружении сборки DeepOS с mtools и device-tree-compiler подставить
пути к архиву Arch‑R Clone, оверлею V20 и собранному squashfs DeepOS.

```sh
donor=/path/to/ArchR-clone.img.gz
overlay=/path/to/mipi-panel.dtbo
rootfs=build/rootfs.squashfs
python3 tools/prepare-v20-kernel.py --archr-image "$donor" --panel-overlay "$overlay" --out build/v20-hw-kernel
python3 tools/mkboot.py --kernel build/v20-hw-kernel/Image --dtb build/v20-hw-kernel/rk3326-r36s-v20.dtb --out build/boot-v20 --extlinux board/r36s-v20/boot/extlinux/archr-v20.conf --boot-script board/r36s-v20/boot/boot.cmd
python3 tools/mkimage.py --out build/deepos-v20-test.img --size-mib 4096 --boot build/boot-v20 --sys-a "$rootfs" --loader-donor "$donor"
python3 tools/preflight.py --root . --kernel build/v20-hw-kernel/Image --dtb build/v20-hw-kernel/rk3326-r36s-v20.dtb --boot build/boot-v20 --rootfs "$rootfs" --image build/deepos-v20-test.img --loader-donor "$donor"
```

Проверка на устройстве начинается с журнала UART от включения, файла
`BOOT/report/boot.txt` и первого кадра DeepOS. Фактические замеры
загрузки, памяти и температур пока недоступны.
