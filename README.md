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
