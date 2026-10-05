# Получение скриншота экрана телефона

нужна команда adb (android debug bridge) - для подклбчения к телефону и его отладки; кроме прочего можно будет сделать скриншоты и не сохранять их на телефоне


adb shell - вызов консоли; 

screencap - делаем скрин 

```
> adb shell
a54x:/ $ screencap --help

usage: screencap [-ahp] [-d display-id] [FILENAME]
   -h: this message
   -a: captures all the active displays. This appends an integer postfix to the FILENAME.
       e.g., FILENAME_0.png, FILENAME_1.png. If both -a and -d are given, it ignores -d.
   -d: specify the display ID to capture (If the id is not given, it defaults to 4633128672291735932)
       see "dumpsys SurfaceFlinger --display-id" for valid display IDs.
   -p: outputs in png format.
   --preserve-display-colors: Set to true to preserves the native display colorspace. Useful
       for mixed HDR + SDR content, using identical processing as the display's

If FILENAME ends with .png it will be saved as a png.
If FILENAME is not given, the results will be printed to stdout.
1|a54x:/ $ 

```

кароч нужен флаг -p для сохранеия  + нужен .png чтобы не возвращало stdout

тогда у нас получается ```adb shell screencap -p "PATH/FILENAME.PNG"```

при поиске нужной папки был послан нахуй

```
> adb shell
a54x:/ $ ls
adb_keys        d               etc                odm          proc                    system
apex            data            init               odm_dlkm     product                 system_dlkm
bin             data_mirror     init.container.rc  oem          sdcard                  system_ext
bootstrap-apex  debug_ramdisk   init.environ.rc    omr          second_stage_resources  tmp
bugreports      dev             linkerconfig       optics       sepolicy_version        vendor
cache           dpolicy_system  metadata           postinstall  storage                 vendor_dlkm
config          efs             mnt                prism        sys
a54x:/ $ cd data/                                                                                          
a54x:/data $ ls
ls: .: Permission denied
1|a54x:/data $ sudo ls 
/system/bin/sh: sudo: inaccessible or not found
127|a54x:/data $ su
/system/bin/sh: su: inaccessible or not found

```

с помощью всевышнего поиск информации не затянулся локальные файлы

```
a54x:/ $ cd sdcard/                                                                                        
a54x:/sdcard $ ls
142x142.grey           Android    Download  Pictures    Ringtones  matan
2_5395404978854599538  DCIM       Movies    Podcasts    TAPK       Внутреннее\ хранилище
Alarms                 Documents  Music     Recordings  VK
a54x:/sdcard $ %   
```

тут можем пакостить 

соответственно соохраняет скрин сюда

и потом удаляем без зарения совести

пообщавшись со всевышним выяснил что
`subprocess.call` хуже чем `subprocess.run`
тк первый показывает только код выполнения а не весь аутпут.

```
> adb shell
a54x:/ $ mkdir --help
Toybox 0.8.12-android multicall binary (see toybox --help)

usage: mkdir [-vp] [-Z context] [-m MODE] [DIR...]

Create one or more directories.

-m	Set permissions of directory to mode
-p	Make parent directories as needed
-v	Verbose
-Z	Set security context
a54x:/ $ 

```

забыл про прикол с несуществующей папкой нужен флаг `-p` чтобы она создавалась без проблем

так заебца скрин есть все работает

нужно перекинуть его на пк в папку tmp

`adb --help`

```
file transfer:
 push [--sync] [-z ALGORITHM] [-Z] LOCAL... REMOTE
     copy local files/directories to device
     --sync: only push files that are newer on the host than the device
     -n: dry run: push files to device without storing to the filesystem
     -z: enable compression with a specified algorithm (any/none/brotli/lz4/zstd)
     -Z: disable compression
 pull [-a] [-z ALGORITHM] [-Z] REMOTE... LOCAL
     copy files/dirs from device
     -a: preserve file timestamp and mode
     -z: enable compression with a specified algorithm (any/none/brotli/lz4/zstd)
     -Z: disable compression
 sync [-l] [-z ALGORITHM] [-Z] [all|data|odm|oem|product|system|system_ext|vendor]
     sync a local build from $ANDROID_PRODUCT_OUT to the device (default all)
     -n: dry run: push files to device without storing to the filesystem
     -l: list files that would be copied, but don't copy them
     -z: enable compression with a specified algorithm (any/none/brotli/lz4/zstd)
     -Z: disable compression
```
хаваем pull допустим с флагом -Z

написали комадну для созадния папки на устройстве 

написали скрипт пылесборник для срина (хавает его с устройства)

флаг `-Z` не обязателен по словам всевышнего тк .png формат и так сжат


прочитали хуйню поняли темплейт и паттер метчинги нам не френды

потому что что потому что в россии нет места кому? - чуркам

![паттерн метчинг](img/readme/result.png)

использует анализ контуров 

так в данный момент я на вражеской территории но пока схржу за своего я не мылся день от меня чуть фонит так что программисты пока приняли за своего надо делать все быстрее

щас нашли контуры объектов 

![контуры](img/readme/contours.png)

прикол работает пока не уверен что будет на всех цветах рабоатть (на блеклых типа мб поднять трешолд)

ну вот тут вроде как даже белый на белом читается осталось их фильтровать 
плохо что их много хорошо что будет все видно и мне не надо будет с бубном танцевать чтобы понять сколько клеток на экране

![контуры2](img/readme/contours2.png)


натыкали нужные контуры +- с 15го до 115) не вкл

![контуры3](img/readme/1791160980.4416482.png)


посовещался с высшим разумом квадратеке можно найти по иерархии и по площади с периметром они одинакове (кто бы мог подумать)


МЫ ТЕПЕРЬ МОДНИКИ АЛО

тут толерантность 500 на всякий надо потестить с уровнями где квадратеке больше тут дельта 165 +-
```
100
delta: 165
array([9100, 9098, 9098, 9019, 9017, 9019, 9100, 9098, 9098, 9018, 9099,
       9094, 9098, 9021, 9019, 9017, 9099, 9094, 9098, 9021, 9098, 9098,
       9098, 9021, 9017, 9019, 9102, 9096, 9097, 9021, 9019, 9017, 9019,
       8941, 8939, 8939, 9019, 9021, 9019, 8937, 9017, 9017, 9017, 8939,
       8945, 8941, 9017, 9019, 9017, 8937, 9019, 9016, 9017, 8941, 8941,
       8941, 9019, 9022, 9017, 8939, 9100, 9099, 9094, 9019, 9019, 9019,
       9100, 9100, 9097, 9016, 9098, 9094, 9098, 9021, 9023, 9016, 9100,
       9096, 9096, 9019, 9097, 9094, 9097, 9021, 9017, 9019, 9097, 9096,
       9096, 9021, 9016, 9017, 9019, 8937, 8939, 8939, 9021, 9022, 9024,
       8937], dtype=uint64)

```
ДА ПОШЛО ВСЕ В ПИЗДУ ХАРДКОДИМ ПИКСЕЛИ НЕ ДАЙ БОГ КТО С ПЛАНШЕТА АЗЙДЕТ
ВСЕМ ПИЗДЫ ДАМ и ваще только у меня работать убдет потому что я для себя писмал бебебебебе


# 0 640
# max 1800


ЮОЖЕ БЛЯТЬ ДА 6 УТРА СУКА Я СДЕЛАЛ ЭЛТО Я НАШЕЛ КООРДИНАТЫ БЛЯДСКИХ ТОЧЕК ДА Я ЗАХАРЖКЛИД НО НАХУЙ МНЕ БОЛЬШЕ ДНЯ НА ЭТОМ СИЖЕЬЬ АААА КАК НА МЕТЕ АААА

![СОСААААААААААТЬ](img/readme/1791172051.9614637.png)


ТАПАЕМ ХОМЯЧКА ТАПАЕМ

adb shell input tap X Y

